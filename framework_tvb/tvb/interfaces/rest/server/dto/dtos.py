# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2020, Baycrest Centre for Geriatric Care ("Baycrest") and others
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

class UserDto:
    def __init__(self, user):
        self.username = user.username
        self.email = user.email
        self.validated = user.validated
        self.role = user.role


class ProjectDto:
    def __init__(self, project):
        self.gid = project.gid
        self.name = project.name
        self.description = project.description
        self.gid = project.gid
        self.version = project.version


class OperationDto:
    def __init__(self, operation):
        self.user_id = operation['user'].id
        self.algorithm_id = operation['algorithm'].id
        self.group = operation['group']
        self.gid = operation['gid']
        self.create_date = operation['create']
        self.start_date = operation['start']
        self.completion_date = operation['complete']
        self.status = operation['status']
        self.visible = operation['visible']


class AlgorithmDto:
    def __init__(self, algorithm):
        self.module = algorithm.module
        self.classname = algorithm.classname
        self.displayname = algorithm.displayname
        self.description = algorithm.description


class DataTypeDto:
    def __init__(self, datatype):
        self.gid = datatype.gid
        self.name = datatype.display_name
        self.type = datatype.display_type
