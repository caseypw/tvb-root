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
# CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
# Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""
Upgrade script from H5 version 4 to version 5 (for tvb release 2.0)

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Robert Vincze <robert.vincze@codemart.ro>
"""

import json
import os
import sys
from datetime import datetime
import numpy
from tvb.adapters.datatypes.h5.annotation_h5 import ConnectivityAnnotationsH5
from tvb.adapters.datatypes.h5.mapped_value_h5 import ValueWrapperH5
from tvb.adapters.simulator.simulator_adapter import SimulatorAdapter
from tvb.core.entities.file.simulator.burst_configuration_h5 import BurstConfigurationH5
from tvb.core.entities.file.simulator.datatype_measure_h5 import DatatypeMeasureH5
from tvb.core.entities.file.simulator.simulation_history_h5 import SimulationHistory
from tvb.core.entities.model.model_burst import BurstConfiguration
from tvb.core.entities.storage import dao
from tvb.core.neocom import h5
from tvb.core.neocom.h5 import REGISTRY
from tvb.basic.logger.builder import get_logger
from tvb.basic.profile import TvbProfile
from tvb.core.entities.file.exceptions import IncompatibleFileManagerException, MissingDataSetException
from tvb.core.entities.file.hdf5_storage_manager import HDF5StorageManager
from tvb.core.entities.transient.structure_entities import DataTypeMetaData
from tvb.core.neotraits._h5accessors import DataSetMetaData
from tvb.core.neotraits._h5core import H5File
from tvb.core.neotraits.h5 import STORE_STRING
from tvb.core.services.import_service import OPERATION_XML, ImportService, Operation2ImportData
from tvb.datatypes.sensors import SensorTypes

LOGGER = get_logger(__name__)
FIELD_SURFACE_MAPPING = "has_surface_mapping"
FIELD_VOLUME_MAPPING = "has_volume_mapping"
GID_PREFIX = "urn:uuid:"


def _lowercase_first_character(string):
    """
    One-line function which converts the first character of a string to lowercase and
    handles empty strings and None values
    """
    return string[:1].lower() + string[1:] if string else ''


def _pop_lengths(root_metadata):
    root_metadata.pop('length_1d')
    root_metadata.pop('length_2d')
    root_metadata.pop('length_3d')
    root_metadata.pop('length_4d')

    return root_metadata


def _pop_common_metadata(root_metadata):
    root_metadata.pop('label_x')
    root_metadata.pop('label_y')
    root_metadata.pop('aggregation_functions')
    root_metadata.pop('dimensions_labels')
    root_metadata.pop('nr_dimensions')


def _bytes_ds_to_string_ds(storage_manager, ds_name):
    bytes_labels = storage_manager.get_data(ds_name)
    string_labels = []
    for i in range(len(bytes_labels)):
        string_labels.append(str(bytes_labels[i], 'utf-8'))

    storage_manager.remove_data(ds_name)
    storage_manager.store_data(ds_name, numpy.asarray(string_labels).astype(STORE_STRING))
    return storage_manager


def _migrate_dataset_metadata(dataset_list, storage_manager):
    for dataset in dataset_list:
        metadata = DataSetMetaData.from_array(storage_manager.get_data(dataset)).to_dict()
        storage_manager.set_metadata(metadata, dataset)
        metadata = storage_manager.get_metadata(dataset)
        if 'Variance' in metadata:
            storage_manager.remove_metadata('Variance', dataset)
        if 'Size' in metadata:
            storage_manager.remove_metadata('Size', dataset)


def _migrate_one_stimuli_param(root_metadata, param_name):
    param = json.loads(root_metadata[param_name])
    new_param = dict()
    new_param['type'] = param['__mapped_class']
    new_param['parameters'] = param['parameters']
    root_metadata[param_name] = json.dumps(new_param)


def _migrate_stimuli(root_metadata, storage_manager, datasets):
    _migrate_one_stimuli_param(root_metadata, 'spatial')
    _migrate_one_stimuli_param(root_metadata, 'temporal')

    for dataset in datasets:
        weights = eval(root_metadata[dataset])
        storage_manager.store_data(dataset, weights)
        _migrate_dataset_metadata([dataset], storage_manager)
        root_metadata.pop(dataset)


def _migrate_time_series(root_metadata, storage_manager, class_name, dependent_attributes):
    root_metadata.pop(FIELD_SURFACE_MAPPING)
    root_metadata.pop(FIELD_VOLUME_MAPPING)
    _pop_lengths(root_metadata)
    metadata = ['data', 'time']

    if class_name != 'TimeSeriesVolume':
        root_metadata['nr_dimensions'] = int(root_metadata['nr_dimensions'])
        root_metadata['sample_rate'] = float(root_metadata['sample_rate'])
    else:
        metadata.pop(1)

    root_metadata['sample_period'] = float(root_metadata['sample_period'])
    root_metadata['start_time'] = float(root_metadata['start_time'])

    root_metadata["sample_period_unit"] = root_metadata["sample_period_unit"].replace("\"", '')
    root_metadata[DataTypeMetaData.KEY_TITLE] = root_metadata[DataTypeMetaData.KEY_TITLE].replace("\"", '')
    _migrate_dataset_metadata(metadata, storage_manager)

    if class_name == 'TimeSeriesRegion':
        root_metadata['region_mapping'] = GID_PREFIX + root_metadata['region_mapping']
        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']

        dependent_attributes['connectivity'] = root_metadata['connectivity']
        dependent_attributes['region_mapping'] = root_metadata['region_mapping']
    elif class_name == 'TimeSeriesSurface':
        root_metadata['surface'] = GID_PREFIX + root_metadata['surface']
        dependent_attributes['surface'] = root_metadata['surface']
    elif class_name in ['TimeSeriesEEG', 'TimeSeriesMEG', 'TimeSeriesSEEG']:
        root_metadata['sensors'] = GID_PREFIX + root_metadata['sensors']
        dependent_attributes['sensors'] = root_metadata['sensors']
    else:
        root_metadata['volume'] = GID_PREFIX + root_metadata['volume']
        dependent_attributes['volume'] = root_metadata['volume']
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('sample_rate')

    return dependent_attributes


def _create_new_burst(burst_params, root_metadata):
    burst_config = BurstConfiguration(burst_params['fk_project'])
    burst_config.datatypes_number = burst_params['datatypes_number']
    burst_config.dynamic_ids = burst_params['dynamic_ids']
    burst_config.error_message = burst_params['error_message']
    burst_config.finish_time = datetime.strptime(burst_params['finish_time'], '%Y-%m-%d %H:%M:%S.%f')
    burst_config.fk_metric_operation_group = burst_params['fk_metric_operation_group']
    burst_config.fk_operation_group = burst_params['fk_operation_group']
    burst_config.fk_project = burst_params['fk_project']
    burst_config.fk_simulation = burst_params['fk_simulation']
    burst_config.name = burst_params['name']
    burst_config.range_1 = burst_params['range_1']
    burst_config.range_2 = burst_params['range_2']
    burst_config.start_time = datetime.strptime(burst_params['start_time'], '%Y-%m-%d %H:%M:%S.%f')
    burst_config.status = burst_params['status']
    root_metadata['parent_burst'] = GID_PREFIX + burst_config.gid

    return burst_config


def update(input_file):
    """
    :param input_file: the file that needs to be converted to a newer file storage version.
    """

    # The first step is to check based on the path if this function call is part of the migration of the whole storage
    # folder or just one datatype (in the first case the second to last element in the path is a number
    split_path = input_file.split(os.path.sep)
    storage_migrate = True
    try:
        # Change file names only for storage migration
        op_id = int(split_path[-2])

        file_basename = os.path.basename(input_file)
        replaced_basename = file_basename.replace('-', '')
        replaced_basename = replaced_basename.replace('BrainSkull', 'Surface')
        replaced_basename = replaced_basename.replace('CorticalSurface', 'Surface')
        replaced_basename = replaced_basename.replace('SkinAir', 'Surface')
        replaced_basename = replaced_basename.replace('BrainSkull', 'Surface')
        replaced_basename = replaced_basename.replace('SkullSkin', 'Surface')
        replaced_basename = replaced_basename.replace('EEGCap', 'Surface')
        replaced_basename = replaced_basename.replace('FaceSurface', 'Surface')
        replaced_basename = replaced_basename.replace('SensorsEEG', 'Sensors')
        replaced_basename = replaced_basename.replace('SensorsMEG', 'Sensors')
        replaced_basename = replaced_basename.replace('SensorsInternal', 'Sensors')
        replaced_basename = replaced_basename.replace('ProjectionSurfaceEEG', 'ProjectionMatrix')
        replaced_basename = replaced_basename.replace('ProjectionSurfaceMEG', 'ProjectionMatrix')
        replaced_basename = replaced_basename.replace('ProjectionSurfaceSEEG', 'ProjectionMatrix')
        new_file_path = os.path.join(input_file, os.pardir, replaced_basename)
        os.rename(input_file, new_file_path)
        input_file = new_file_path
    except ValueError:
        op_id = None
        storage_migrate = False

    if not os.path.isfile(input_file):
        raise IncompatibleFileManagerException("Not yet implemented update for file %s" % input_file)

    # Obtain storage manager and metadata
    folder, file_name = os.path.split(input_file)
    storage_manager = HDF5StorageManager(folder, file_name)
    root_metadata = storage_manager.get_metadata()

    if DataTypeMetaData.KEY_CLASS_NAME not in root_metadata:
        raise IncompatibleFileManagerException("File %s received for upgrading 4 -> 5 is not valid, due to missing "
                                               "metadata: %s" % (input_file, DataTypeMetaData.KEY_CLASS_NAME))

    # In the new format all metadata has the 'TVB_%' format, where '%' starts with a lowercase letter
    lowercase_keys = []
    for key, value in root_metadata.items():
        root_metadata[key] = str(value, 'utf-8')
        lowercase_keys.append(_lowercase_first_character(key))
        storage_manager.remove_metadata(key)

    # Update DATA_VERSION
    root_metadata = dict(zip(lowercase_keys, list(root_metadata.values())))
    root_metadata[TvbProfile.current.version.DATA_VERSION_ATTRIBUTE] = TvbProfile.current.version.DATA_VERSION
    class_name = root_metadata["type"]

    # UPDATE CREATION DATE
    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace('datetime:', '')
    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace(':', '-')
    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace(' ', ',')

    # OBTAIN THE MODULE (for a few data types the old module doesn't exist anymore, in those cases the attr
    # will be set later
    try:
        datatype_class = getattr(sys.modules[root_metadata["module"]],
                                 root_metadata["type"])
        h5_class = REGISTRY.get_h5file_for_datatype(datatype_class)
        root_metadata[H5File.KEY_WRITTEN_BY] = h5_class.__module__ + '.' + h5_class.__name__
    except KeyError:
        h5_class = None

    # Other general modifications
    root_metadata['user_tag_1'] = ''
    root_metadata['gid'] = GID_PREFIX + root_metadata['gid']
    root_metadata.pop("type")
    root_metadata.pop("module")
    root_metadata.pop('data_version')

    dependent_attributes = {}  # where is the case the datatype will have a dict of the datatype it depends on
    # attr in the old DB, those changed will be marked in this dict

    files_in_folder = os.listdir(folder)
    import_service = ImportService()
    algorithm = ''

    operation_xml_parameters = {}  # params that are needed for the view_model but are not in the Operation.xml file
    additional_params = {}  # params that can't be jsonified with json.dumps
    has_vm = False
    operation = None
    # Take information out from the Operation.xml file
    if OPERATION_XML in files_in_folder:
        operation_file_path = os.path.join(folder, OPERATION_XML)
        project = dao.get_project_by_name(split_path[-3])
        xml_operation, operation_xml_parameters, algorithm = \
            import_service.build_operation_from_file(project, operation_file_path)
        operation = dao.get_operation_by_id(op_id)
        try:
            operation_xml_parameters = eval(operation_xml_parameters)
        except NameError:
            operation_xml_parameters = operation_xml_parameters.replace('null', '\"null\"')
            operation_xml_parameters = eval(operation_xml_parameters)
    else:
        has_vm = True

    # HERE STARTS THE PART WHICH IS SPECIFIC TO EACH H5 FILE #

    if class_name == 'Connectivity':
        root_metadata['number_of_connections'] = int(root_metadata['number_of_connections'])
        root_metadata['number_of_regions'] = int(root_metadata['number_of_regions'])

        if root_metadata['undirected'] == "0":
            root_metadata['undirected'] = "bool:False"
        else:
            root_metadata['undirected'] = "bool:True"

        if root_metadata['saved_selection'] == 'null':
            root_metadata['saved_selection'] = '[]'

        metadata = ['centres', 'region_labels', 'tract_lengths', 'weights']
        extra_metadata = ['orientations', 'areas', 'cortical', 'hemispheres', 'orientations']

        for mt in extra_metadata:
            try:
                storage_manager.get_metadata(mt)
                metadata.append(mt)
            except MissingDataSetException:
                pass

        if operation_xml_parameters['normalization'] == 'none':
            del operation_xml_parameters['normalization']

        storage_manager.remove_metadata('Mean non zero', 'tract_lengths')
        storage_manager.remove_metadata('Min. non zero', 'tract_lengths')
        storage_manager.remove_metadata('Var. non zero', 'tract_lengths')
        storage_manager.remove_metadata('Mean non zero', 'weights')
        storage_manager.remove_metadata('Min. non zero', 'weights')
        storage_manager.remove_metadata('Var. non zero', 'weights')

        _migrate_dataset_metadata(metadata, storage_manager)

    elif class_name in ['BrainSkull', 'CorticalSurface', 'SkinAir', 'BrainSkull', 'SkullSkin', 'EEGCap', 'FaceSurface']:
        root_metadata['edge_max_length'] = float(root_metadata['edge_max_length'])
        root_metadata['edge_mean_length'] = float(root_metadata['edge_mean_length'])
        root_metadata['edge_min_length'] = float(root_metadata['edge_min_length'])
        root_metadata['number_of_split_slices'] = int(root_metadata['number_of_split_slices'])
        root_metadata['number_of_triangles'] = int(root_metadata['number_of_triangles'])
        root_metadata['number_of_vertices'] = int(root_metadata['number_of_vertices'])

        root_metadata['zero_based_triangles'] = "bool:" + root_metadata['zero_based_triangles'][:1].upper() \
                                                + root_metadata['zero_based_triangles'][1:]
        root_metadata['bi_hemispheric'] = "bool:" + root_metadata['bi_hemispheric'][:1].upper() \
                                          + root_metadata['bi_hemispheric'][1:]
        root_metadata['valid_for_simulations'] = "bool:" + root_metadata['valid_for_simulations'][:1].upper() \
                                                 + root_metadata['valid_for_simulations'][1:]

        root_metadata["surface_type"] = root_metadata["surface_type"].replace("\"", '')

        if root_metadata['zero_based_triangles'] == 'bool:True':
            operation_xml_parameters['zero_based_triangles'] = True
        else:
            operation_xml_parameters['zero_based_triangles'] = False

        storage_manager.store_data('split_triangles', [])

        _migrate_dataset_metadata(['split_triangles', 'triangle_normals', 'triangles', 'vertex_normals', 'vertices'],
                                  storage_manager)

    elif class_name == 'RegionMapping':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)

        root_metadata['surface'] = GID_PREFIX + root_metadata['surface']
        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']
        dependent_attributes['surface'] = root_metadata['surface']
        algorithm = algorithm.replace('RegionMapping_Importer', 'RegionMappingImporter')

    elif class_name == 'RegionVolumeMapping':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)

        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']
        root_metadata['volume'] = GID_PREFIX + root_metadata['volume']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']
        dependent_attributes['volume'] = root_metadata['volume']

    elif 'Sensors' in class_name:
        root_metadata['number_of_sensors'] = int(root_metadata['number_of_sensors'])
        root_metadata['sensors_type'] = root_metadata["sensors_type"].replace("\"", '')
        root_metadata['has_orientation'] = "bool:" + root_metadata['has_orientation'][:1].upper() \
                                           + root_metadata['has_orientation'][1:]

        storage_manager.remove_metadata('Size', 'labels')
        storage_manager.remove_metadata('Size', 'locations')
        storage_manager.remove_metadata('Variance', 'locations')
        storage_manager = _bytes_ds_to_string_ds(storage_manager, 'labels')

        datasets = ['labels', 'locations']

        if 'MEG' in class_name:
            storage_manager.remove_metadata('Size', 'orientations')
            storage_manager.remove_metadata('Variance', 'orientations')
            datasets.append('orientations')
            operation_xml_parameters['sensors_type'] = SensorTypes.TYPE_MEG.value
        elif 'EEG' in class_name:
            operation_xml_parameters['sensors_type'] = SensorTypes.TYPE_EEG.value
        else:
            operation_xml_parameters['sensors_type'] = SensorTypes.TYPE_INTERNAL.value

        _migrate_dataset_metadata(datasets, storage_manager)
        algorithm = algorithm.replace('Sensors_Importer', 'SensorsImporter')

    elif 'Projection' in class_name:
        root_metadata['sensors'] = GID_PREFIX + root_metadata['sensors']
        root_metadata['sources'] = GID_PREFIX + root_metadata['sources']
        root_metadata['written_by'] = "tvb.adapters.datatypes.h5.projections_h5.ProjectionMatrixH5"
        root_metadata['projection_type'] = root_metadata["projection_type"].replace("\"", '')

        storage_manager.remove_metadata('Size', 'projection_data')
        storage_manager.remove_metadata('Variance', 'projection_data')

        operation_xml_parameters['projection_file'] = input_file

        _migrate_dataset_metadata(['projection_data'], storage_manager)
        dependent_attributes['sensors'] = root_metadata['sensors']
        dependent_attributes['sources'] = root_metadata['sources']
        algorithm = algorithm.replace('BrainstormGainMatrixImporter', 'ProjectionMatrixSurfaceEEGImporter')

    elif class_name == 'LocalConnectivity':
        root_metadata['cutoff'] = float(root_metadata['cutoff'])
        root_metadata['surface'] = GID_PREFIX + root_metadata['surface']

        # storage_manager.remove_metadata('shape', 'matrix')
        matrix_metadata = storage_manager.get_metadata('matrix')
        matrix_metadata['Shape'] = str(matrix_metadata['Shape'], 'utf-8')
        matrix_metadata['dtype'] = str(matrix_metadata['dtype'], 'utf-8')
        matrix_metadata['format'] = str(matrix_metadata['format'], 'utf-8')
        storage_manager.set_metadata(matrix_metadata, 'matrix')

        equation = eval(root_metadata['equation'])
        equation['type'] = equation['__mapped_class']
        del equation['__mapped_class']
        del equation['__mapped_module']

        root_metadata['equation'] = json.dumps(equation)

        operation_xml_parameters['surface'] = root_metadata['surface']
        dependent_attributes['surface'] = root_metadata['surface']

    elif class_name == 'ConnectivityAnnotations':
        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']
        root_metadata['written_by'] = "tvb.adapters.datatypes.h5.annotation_h5.ConnectivityAnnotationsH5"
        h5_class = ConnectivityAnnotationsH5

        _migrate_dataset_metadata(['region_annotations'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']

    elif 'TimeSeries' in class_name:
        operation_xml_parameters.pop('', None)
        if 'surface' in operation_xml_parameters and operation_xml_parameters['surface'] == '':
            operation_xml_parameters['surface'] = None
        if 'stimulus' in operation_xml_parameters and operation_xml_parameters['stimulus'] == '':
            operation_xml_parameters['stimulus'] = None
        dependent_attributes = _migrate_time_series(root_metadata, storage_manager,
                                                    class_name, dependent_attributes)
    elif 'Volume' in class_name:
        root_metadata['voxel_unit'] = root_metadata['voxel_unit'].replace("\"", '')

        if operation_xml_parameters['connectivity'] == '':
            operation_xml_parameters['connectivity'] = None

        _migrate_dataset_metadata(['origin', 'voxel_size'], storage_manager)

    elif class_name == 'StructuralMRI':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)

        root_metadata['volume'] = GID_PREFIX + root_metadata['volume']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['volume'] = root_metadata['volume']

    elif class_name == 'ComplexCoherenceSpectrum':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['epoch_length'] = float(root_metadata['epoch_length'])
        root_metadata['segment_length'] = float(root_metadata['segment_length'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']
        root_metadata['windowing_function'] = root_metadata['windowing_function'].replace("\"", '')
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        _migrate_dataset_metadata(['array_data', 'cross_spectrum'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'WaveletCoefficients':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['q_ratio'] = float(root_metadata['q_ratio'])
        root_metadata['sample_period'] = float(root_metadata['sample_period'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']
        root_metadata['mother'] = root_metadata['mother'].replace("\"", '')
        root_metadata['normalisation'] = root_metadata['normalisation'].replace("\"", '')

        operation_xml_parameters['input_data'] = root_metadata['source']

        _migrate_dataset_metadata(['amplitude', 'array_data', 'frequencies', 'phase', 'power'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'CoherenceSpectrum':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['nfft'] = int(root_metadata['nfft'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        array_data = storage_manager.get_data('array_data')
        storage_manager.remove_data('array_data')
        storage_manager.store_data('array_data', numpy.asarray(array_data, dtype=numpy.float64))

        _migrate_dataset_metadata(['array_data', 'frequency'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'CrossCorrelation':
        operation_xml_parameters['datatype'] = root_metadata['source']
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        dependent_attributes['source'] = root_metadata['source']
        _migrate_dataset_metadata(['array_data', 'time'], storage_manager)

    elif class_name == 'Fcd':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['sp'] = float(root_metadata['sp'])
        root_metadata['sw'] = float(root_metadata['sw'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'FourierSpectrum':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['segment_length'] = float(root_metadata['segment_length'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']
        operation_xml_parameters['input_data'] = root_metadata['source']

        _migrate_dataset_metadata(['amplitude', 'array_data', 'average_power',
                                   'normalised_average_power', 'phase', 'power'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'IndependentComponents':
        root_metadata['n_components'] = int(root_metadata['n_components'])
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        _migrate_dataset_metadata(['component_time_series', 'mixing_matrix', 'norm_source',
                                   'normalised_component_time_series', 'prewhitening_matrix',
                                   'unmixing_matrix'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'CorrelationCoefficients':
        _pop_lengths(root_metadata)
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)

        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        operation_xml_parameters['datatype'] = root_metadata['source']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'PrincipalComponents':
        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        _migrate_dataset_metadata(['component_time_series', 'fractions',
                                   'norm_source', 'normalised_component_time_series',
                                   'weights'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'Covariance':
        _pop_common_metadata(root_metadata)
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['source'] = GID_PREFIX + root_metadata['source']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['source'] = root_metadata['source']

    elif class_name == 'ConnectivityMeasure':
        _pop_common_metadata(root_metadata)
        _pop_lengths(root_metadata)
        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']

        operation_xml_parameters['data_file'] = input_file
        operation_xml_parameters['connectivity'] = root_metadata['connectivity']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']

    # TODO: Make sure DatatypeMeasureH5 is converted after a DatatypeMeasure class is created and then remove the return
    elif class_name == 'DatatypeMeasure':
        root_metadata['written_by'] = 'tvb.core.entities.file.simulator.datatype_measure_h5.DatatypeMeasureH5'
        h5_class = DatatypeMeasureH5
        dependent_attributes['analyzed_datatype'] = root_metadata['analyzed_datatype']
        return

    elif class_name == 'StimuliRegion':
        root_metadata['connectivity'] = GID_PREFIX + root_metadata['connectivity']
        additional_params['weight'] = numpy.asarray(eval(root_metadata['weight']), dtype=numpy.float64)
        _migrate_stimuli(root_metadata, storage_manager, ['weight'])
        dependent_attributes['connectivity'] = root_metadata['connectivity']

    elif class_name == 'StimuliSurface':
        root_metadata['surface'] = GID_PREFIX + root_metadata['surface']
        additional_params['focal_points_triangles'] = numpy.asarray(eval(root_metadata['focal_points_triangles']),
                                                                    dtype=numpy.int)
        _migrate_stimuli(root_metadata, storage_manager, ['focal_points_surface', 'focal_points_triangles'])
        dependent_attributes['surface'] = root_metadata['surface']

    elif class_name == 'ValueWrapper':
        root_metadata['data_type'] = root_metadata['data_type'].replace("\"", '')
        root_metadata['written_by'] = "tvb.adapters.datatypes.h5.mapped_value_h5.ValueWrapperH5"
        h5_class = ValueWrapperH5

    elif class_name == 'SimulationState':
        os.remove(input_file)
        return

    root_metadata['operation_tag'] = ''
    storage_manager.set_metadata(root_metadata)

    if storage_migrate is False:
        return

    with h5_class(input_file) as f:

        # Create the corresponding datatype to be stored in db
        datatype = REGISTRY.get_datatype_for_h5file(f)()
        f.load_into(datatype)
        generic_attributes = f.load_generic_attributes()
        datatype_index = REGISTRY.get_index_for_datatype(datatype.__class__)()
        datatype_index.create_date = root_metadata['create_date']

        # Get the dependent datatypes
        for attr_name, attr_value in dependent_attributes.items():
            dependent_datatype_index = dao.get_datatype_by_gid(attr_value.replace('-', '').replace('urn:uuid:', ''))
            dependent_datatype = h5.load_from_index(dependent_datatype_index)
            setattr(datatype, attr_name, dependent_datatype)

        if has_vm is False:
            # Get parent_burst when needed
            if 'time_series' in operation_xml_parameters:
                ts = dao.get_datatype_by_gid(
                    operation_xml_parameters['time_series'].replace('-', '').replace('urn:uuid:', ''))
                root_metadata['parent_burst'] = GID_PREFIX + ts.fk_parent_burst
                storage_manager.set_metadata(root_metadata)

            alg_json = json.loads(algorithm)
            algorithm = dao.get_algorithm_by_module(alg_json['module'], alg_json['classname'])
            operation.algorithm = algorithm
            operation.fk_from_algo = algorithm.id

            operation_xml_parameters = json.dumps(operation_xml_parameters)
            operation_data = Operation2ImportData(operation, folder, info_from_xml=operation_xml_parameters)
            operation_entity, _ = import_service.import_operation(operation_data.operation)
            possible_burst_id = operation.view_model_gid
            vm = import_service.create_view_model(operation, operation_data, folder, additional_params)

            if 'TimeSeries' in class_name:
                alg = SimulatorAdapter().view_model_to_has_traits(vm)
                alg.preconfigure()
                alg.configure()
                simulation_history = SimulationHistory()
                simulation_history.populate_from(alg)
                history_index = h5.store_complete(simulation_history, folder, vm.generic_attributes)
                dao.store_entity(history_index)

                burst_params = dao.get_burst_for_migration(possible_burst_id)
                if burst_params is not None:
                    burst_config = _create_new_burst(burst_params, root_metadata)
                    burst_config.simulator_gid = vm.gid.hex
                    generic_attributes.parent_burst = burst_config.gid

                    # Creating BurstConfigH5
                    with BurstConfigurationH5(os.path.join(input_file, os.pardir, 'BurstConfiguration_'
                                                                                  + burst_config.gid + ".h5")) as f:
                        f.store(burst_config)

                    dao.store_entity(burst_config)
                    root_metadata['parent_burst'] = GID_PREFIX + burst_config.gid
                    storage_manager.set_metadata(root_metadata)

            os.remove(os.path.join(folder, OPERATION_XML))

        # Populate datatype
        datatype_index.fill_from_has_traits(datatype)
        datatype_index.fill_from_generic_attributes(generic_attributes)
        datatype_index.fk_from_operation = op_id

    # Finally store new datatype in db
    dao.store_entity(datatype_index)
