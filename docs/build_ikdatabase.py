# -*- coding: utf-8 -*-
# Copyright (C) 2011 Rosen Diankov (rosen.diankov@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from openravepy import *
from numpy import *
from optparse import OptionParser
import os
import scipy

imagedir = 'images/robots'#build/en/main/_images/robots'
imagelinkdir = '../../images/robots'

def buildrobot(outputdir, env, robotfilename, robotstats):
    width=640
    height=480
    focal = 1000.0
    robotname = os.path.split(os.path.splitext(robotfilename)[0])[1]
    imagename = '%s.x.jpg'%robotname
    if env is not None:
        env.Reset()
        r=env.ReadRobotXMLFile(robotfilename)
        if r is None:
            print 'failed ',robotfilename
        else:
            print 'processing ',robotname
            env.AddRobot(r)
            # transform the robot so we don't render it at its axis aligned (white robots completely disappear)
            r.SetTransform(matrixFromQuat(quatRotateDirection([-1,0,0],[-1,1,0.5])))
            ab = r.ComputeAABB()
            K=[focal,focal,width/2,height/2]
            L = ab.extents()[0] + max(ab.extents()[1]*focal/(0.5*width),ab.extents()[2]*focal/(0.5*height))
            Tx=transformLookat(lookat=ab.pos(),camerapos=ab.pos()-array([-1.0,0,0])*L,cameraup=[0,0,-1])
            Ix = viewer.GetCameraImage(width=width,height=height,transform=Tx,K=K)
            L = ab.extents()[1] + max(ab.extents()[0]*focal/(0.5*width),ab.extents()[2]*focal/(0.5*height))
            Ty=transformLookat(lookat=ab.pos(),camerapos=ab.pos()-array([0,1.0,0])*L,cameraup=[0,0,-1])
            Iy = viewer.GetCameraImage(width=width,height=height,transform=Ty,K=K)
            scipy.misc.pilutil.imsave(os.path.join(imagedir,imagename),hstack([Ix,Iy]))

    robotlink = 'robot-'+robotname
    robotxml = """.. _%s:\n\n%s Robot\n%s======

  :filename: %s

.. image:: %s/%s
  :height: 300

"""%(robotlink,robotname,'='*len(robotname),robotfilename, imagelinkdir,imagename)

    prevmanipname = None
    previktypestr = None
    rownames = []
    for manipname, iktypestr, description, sourcefilename, meantime, maxtime, successrate, wrongrate in robotstats:
        if prevmanipname != manipname:
            name = '**' + manipname + '** Manipulator'
            robotxml += name + '\n' + '-'*len(name) + '\n\n'
            prevmanipname = manipname
        if previktypestr != iktypestr:
            name = iktypestr + ' IK'
            robotxml += name + '\n' + '~'*len(name) + '\n\n'
            previktypestr = iktypestr
        rows = []
        rows.append(['success rate','wrong rate','mean time (s)','max time (s)'])
        rows.append(['%.3f'%successrate,'%.3f'%wrongrate,'%.6f'%meantime,'%.6f'%maxtime])
        colwidths = [max([len(row[i]) for row in rows]) for i in range(len(rows[0]))]
        for row in rows:
            for i in range(len(row)):
                row[i] = row[i].ljust(colwidths[i])+'|'
            row[0] = '|'+row[0]
        seprow = ['-'*colwidth + '+' for colwidth in colwidths]
        seprow[0] = '+'+seprow[0]
        rows.insert(0,seprow)
        rows.insert(2,seprow)
        rows.append(seprow)
        robotxml += '**%s**\n\n'%description[0]
        for row in rows:
            robotxml += ''.join(row)+'\n'
        robotxml += '\n\n'
    open(os.path.join(outputdir,robotname+'.rst'),'w').write(robotxml)
    returnxml = """
:ref:`%s`
%s

  :IK parameterizations: %d

.. image:: %s/%s
  :height: 200

----

"""%(robotlink,'-'*(len(robotlink)+7),len(robotstats),imagelinkdir,imagename)
    return returnxml,robotname

def build(allstats,options,outputdir,env):
    mkdir_recursive(outputdir)

    # write each robot
    robotdict = dict()
    for stat in allstats:
        if len(stat) == 9:
            if not stat[0] in robotdict:
                robotdict[stat[0]] = []
            robotdict[stat[0]].append(stat[1:])
    robotxml = ''
    robotnames = []
    for robotfilename, robotstats in robotdict.iteritems():
        xml,robotname = buildrobot(outputdir,env,robotfilename, robotstats)
        robotxml += xml
        robotnames.append(robotname)

    iktypes = ', '.join(iktype.name for iktype in IkParameterization.Type.values.values())
    text="""
.. _ikfast-database:

IKFast Robot Database
=====================

.. htmlonly::

   :Release: **%s**

A collection for robots and statistics for the compiled inverse kinematics files using :ref:`ikfast_compiler`.

This database contains all possible IKs for each robot's manipulator and is automatically generated by the `OpenRAVE Testing Server`_ for each OpenRAVE release.

URL links to the robot files, genreated ik files, and test results history are provided.

.. toctree::
  :maxdepth: 1
  
  testing

* :ref:`Supported inverse kinematics types <ikfast_types>`

The following results originate from `this run <%s>`_.

Robots
======

%s

"""%(ikfast.__version__,options.jenkinsbuild_url,robotxml)
    text += """
List
----

.. toctree::
  :maxdepth: 1

"""
    for robotname in robotnames:
        text += '  %s\n'%robotname
    open(os.path.join(outputdir,'index.rst'),'w').write(text)

    freeparameters = ', '.join('%s free - %s tests'%(i,num) for i,num in enumerate(options.numiktests))
    testing_text="""
.. _ikfast-testing:

IKFast Performance Testing
==========================

There are four different ways of calling the IK solver:

* GetSolution(*goal*) - call with just the end effector parameterization, return the first solution found within limits.
* GetSolution(*goal*,*free*) - call with end effector parameterization and specify all free joint values, return the first solution found within limits.
* GetSolutions(*goal*) - call with just the end effector parameterization, return all solutions searching through all free joint values.
* GetSolutions(*goal*,*free*) - call with end effector parameterization and specify all free joint values, return all possible solutions.

The following algorithm tests these four calls by:

1. Randomly sample a robot configuration and compute the correct parameterization of the end effector *goal* and free joint values *free*.
2. Move the robot to a random position.
3. Call GetSolution(*goal*), GetSolutions(*goal*), GetSolutions(*goal*,*free*)
4. Call GetSolution(*goal*,*free_random*) and GetSolutions(*goal*,*free_random*). Check that the returned solutions have same values as free parameters.

For every end effector parameterization and a returned solution, set the returned solution on the robot and compute the error between the original end effector and the new end effector. If the error is *greater than %f*, then the IK is wrong and the iteration is a *failure*. If no wrong solutions were returned and at least one correct IK solution is found within limits, then the iteration is a *success*. When the free values are not specified, the IK solver will discretize the range of the freevalues and test with all possible combinations [1]_. 

The number of tests is determined by the number of free parameters: %s

Four values are extracted to measure the performance of a generated IK solver:

* wrong rate - number of parameterizations where at least one wrong solution was returned.
* success rate - number of parameterizations where all returned solutions are correct
* no solution rate - number of parameterizations where no solutions were found within limits
* missing solution rate - number of parameterizations where the specific sampled solution was not returned, but at least one solution was found.

An IK is **successful** if the wrong rate is 0, success rate is > %f, and the no solution rate is < %f. 
The raw function call run-time is also recorded.

Degenerate configurations can frequently occur when the robot axes align, this produces a lot of divide by zero conditions inside the IK. In order to check all such code paths, the configuration sampler common tests angles 0, pi/2, pi, and -pi/2.

.. [1] The discretization of the free joint values depends on the robot manipulator and is given in each individual manipulator page.
"""%(options.errorthreshold,freeparameters,options.minimumsuccess,options.maximumnosolutions)
    open(os.path.join(outputdir,'testing.rst'),'w').write(testing_text)

if __name__ == "__main__":
    mkdir_recursive(imagedir)
    allstats,options = pickle.load(open('ikfaststats.pp','r'))
    env=Environment()
    try:
        env.SetViewer('qtcoin',False)
        viewer=env.GetViewer()
        build(allstats,options,'en/ikfast',env)
    finally:
        RaveDestroy()
