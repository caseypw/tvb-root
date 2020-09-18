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
import numpy
from tvb.adapters.analyzers.fcd_adapter import FCDAdapterModel
from tvb.adapters.analyzers.ica_adapter import ICAAdapterModel
from tvb.adapters.analyzers.metrics_group_timeseries import TimeseriesMetricsAdapterModel
from tvb.adapters.analyzers.node_coherence_adapter import NodeCoherenceModel
from tvb.adapters.analyzers.node_complex_coherence_adapter import NodeComplexCoherenceModel
from tvb.adapters.analyzers.node_covariance_adapter import NodeCovarianceAdapterModel
from tvb.adapters.analyzers.pca_adapter import PCAAdapterModel
from tvb.adapters.creators.local_connectivity_creator import LocalConnectivityCreatorModel
from tvb.adapters.creators.stimulus_creator import RegionStimulusCreatorModel, SurfaceStimulusCreatorModel
from tvb.adapters.datatypes.h5.annotation_h5 import ConnectivityAnnotationsH5
from tvb.adapters.uploaders.brco_importer import BRCOImporterModel
from tvb.adapters.uploaders.connectivity_measure_importer import ConnectivityMeasureImporterModel
from tvb.adapters.uploaders.projection_matrix_importer import ProjectionMatrixImporterModel
from tvb.adapters.uploaders.region_mapping_importer import RegionMappingImporterModel
from tvb.adapters.uploaders.sensors_importer import SensorsImporterModel
from tvb.adapters.uploaders.zip_connectivity_importer import ZIPConnectivityImporterModel
from tvb.adapters.uploaders.zip_surface_importer import ZIPSurfaceImporterModel
from tvb.adapters.visualizers.cross_correlation import CrossCorrelationVisualizerModel
from tvb.adapters.visualizers.fourier_spectrum import FourierSpectrumModel
from tvb.adapters.visualizers.wavelet_spectrogram import WaveletSpectrogramVisualizerModel
from tvb.basic.neotraits.ex import TraitTypeError, TraitAttributeError
from tvb.core.entities.file.simulator.view_model import SimulatorAdapterModel
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


LOGGER = get_logger(__name__)
FIELD_SURFACE_MAPPING = "has_surface_mapping"
FIELD_VOLUME_MAPPING = "has_volume_mapping"

REBUILDABLE_TABLES = ['CoherenceSpectrum', 'ComplexCoherenceSpectrum', 'ConnectivityAnnotations', 'Connectivity',
                      'ConnectivityMeasure', 'CorrelationCoeficient', 'Covariance', 'CrossCorrelation',
                      'Fcd', 'FourierSpectrum', 'TimeSeriesRegion', 'BrainSkull', 'CorticalSurface', 'SkinAir',
                      'BrainSkull', 'SkullSkin', 'EEGCap', 'FaceSurface', 'RegionMapping', 'LocalConnectivity']


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
        conn_metadata = DataSetMetaData.from_array(storage_manager.get_data(dataset)).to_dict()
        storage_manager.set_metadata(conn_metadata, dataset)
        metadata = storage_manager.get_metadata(dataset)
        if 'Variance' in metadata:
            storage_manager.remove_metadata('Variance', dataset)
        if 'Size' in metadata:
            storage_manager.remove_metadata('Size',dataset)


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


def update(input_file):
    """
    :param input_file: the file that needs to be converted to a newer file storage version.
    """
    replaced_input_file = input_file.replace('-', '')
    replaced_input_file = replaced_input_file.replace('BrainSkull', 'Surface')
    replaced_input_file = replaced_input_file.replace('CorticalSurface', 'Surface')
    replaced_input_file = replaced_input_file.replace('SkinAir', 'Surface')
    replaced_input_file = replaced_input_file.replace('BrainSkull', 'Surface')
    replaced_input_file = replaced_input_file.replace('SkullSkin', 'Surface')
    replaced_input_file = replaced_input_file.replace('EEGCap', 'Surface')
    replaced_input_file = replaced_input_file.replace('FaceSurface', 'Surface')
    os.rename(input_file, replaced_input_file)
    input_file = replaced_input_file

    if not os.path.isfile(input_file):
        raise IncompatibleFileManagerException("Not yet implemented update for file %s" % input_file)

    folder, file_name = os.path.split(input_file)
    storage_manager = HDF5StorageManager(folder, file_name)

    root_metadata = storage_manager.get_metadata()

    if DataTypeMetaData.KEY_CLASS_NAME not in root_metadata:
        raise IncompatibleFileManagerException("File %s received for upgrading 4 -> 5 is not valid, due to missing "
                                               "metadata: %s" % (input_file, DataTypeMetaData.KEY_CLASS_NAME))

    lowercase_keys = []
    for key, value in root_metadata.items():
        root_metadata[key] = str(value, 'utf-8')
        lowercase_keys.append(_lowercase_first_character(key))
        storage_manager.remove_metadata(key)

    root_metadata = dict(zip(lowercase_keys, list(root_metadata.values())))
    root_metadata[TvbProfile.current.version.DATA_VERSION_ATTRIBUTE] = TvbProfile.current.version.DATA_VERSION
    class_name = root_metadata["type"]

    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace('datetime:', '')
    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace(':', '-')
    root_metadata[DataTypeMetaData.KEY_DATE] = root_metadata[DataTypeMetaData.KEY_DATE].replace(' ', ',')

    try:
        datatype_class = getattr(sys.modules[root_metadata["module"]],
                             root_metadata["type"])
        h5_class = REGISTRY.get_h5file_for_datatype(datatype_class)
        root_metadata[H5File.KEY_WRITTEN_BY] = h5_class.__module__ + '.' + h5_class.__name__
    except KeyError:
        pass

    root_metadata['user_tag_1'] = ''
    root_metadata['gid'] = "urn:uuid:" + root_metadata['gid']

    root_metadata.pop("type")
    root_metadata.pop("module")
    root_metadata.pop('data_version')

    dependent_attributes = {}
    changed_values = {}
    view_model_class = None

    if class_name == 'Connectivity':
        root_metadata['number_of_connections'] = int(root_metadata['number_of_connections'])
        root_metadata['number_of_regions'] = int(root_metadata['number_of_regions'])

        if root_metadata['undirected'] == "0":
            root_metadata['undirected'] = "bool:False"
        else:
            root_metadata['undirected'] = "bool:True"

        if root_metadata['saved_selection'] == 'null':
            root_metadata['saved_selection'] = '[]'

        metadata = ['areas', 'centres', 'orientations', 'region_labels',
                                   'tract_lengths', 'weights']
        try:
            storage_manager.get_metadata('cortical')
            metadata.append('cortical')
        except MissingDataSetException:
            pass

        try:
            storage_manager.get_metadata('hemispheres')
            metadata.append('hemispheres')
        except MissingDataSetException:
            pass

        _migrate_dataset_metadata(metadata, storage_manager)

        storage_manager.remove_metadata('Mean non zero', 'tract_lengths')
        storage_manager.remove_metadata('Min. non zero', 'tract_lengths')
        storage_manager.remove_metadata('Var. non zero', 'tract_lengths')
        storage_manager.remove_metadata('Mean non zero', 'weights')
        storage_manager.remove_metadata('Min. non zero', 'weights')
        storage_manager.remove_metadata('Var. non zero', 'weights')

        view_model_class = ZIPConnectivityImporterModel

    elif class_name in ['BrainSkull', 'CorticalSurface', 'SkinAir', 'BrainSkull', 'SkullSkin', 'EEGCap', 'FaceSurface']:
        root_metadata['edge_max_length'] = float(root_metadata['edge_max_length'])
        root_metadata['edge_mean_length'] = float(root_metadata['edge_mean_length'])
        root_metadata['edge_min_length'] = float(root_metadata['edge_min_length'])

        root_metadata['number_of_split_slices'] = int(root_metadata['number_of_split_slices'])
        root_metadata['number_of_triangles'] = int(root_metadata['number_of_triangles'])
        root_metadata['number_of_vertices'] = int(root_metadata['number_of_vertices'])

        root_metadata["surface_type"] = root_metadata["surface_type"].replace("\"", '')

        storage_manager.store_data('split_triangles', [])

        _migrate_dataset_metadata(['split_triangles', 'triangle_normals', 'triangles', 'vertex_normals', 'vertices'],
                                  storage_manager)

        root_metadata['zero_based_triangles'] = "bool:" + root_metadata['zero_based_triangles'][:1].upper() \
                                                + root_metadata['zero_based_triangles'][1:]
        root_metadata['bi_hemispheric'] = "bool:" + root_metadata['bi_hemispheric'][:1].upper() \
                                          + root_metadata['bi_hemispheric'][1:]
        root_metadata['valid_for_simulations'] = "bool:" + root_metadata['valid_for_simulations'][:1].upper() \
                                                 + root_metadata['valid_for_simulations'][1:]

        if root_metadata['zero_based_triangles'] == 'bool:True':
            changed_values['zero_based_triangles'] = True
        else:
            changed_values['zero_based_triangles'] = False

        view_model_class = ZIPSurfaceImporterModel

    elif class_name == 'RegionMapping':
        root_metadata = _pop_lengths(root_metadata)
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')

        root_metadata['surface'] = "urn:uuid:" + root_metadata['surface']
        root_metadata['connectivity'] = "urn:uuid:" + root_metadata['connectivity']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']
        dependent_attributes['surface'] = root_metadata['surface']

        view_model_class = RegionMappingImporterModel
    elif 'Sensors' in class_name:
        root_metadata['number_of_sensors'] = int(root_metadata['number_of_sensors'])
        root_metadata['sensors_type'] = root_metadata["sensors_type"].replace("\"", '')
        root_metadata['has_orientation'] = "bool:" + root_metadata['has_orientation'][:1].upper() \
                                           + root_metadata['has_orientation'][1:]

        storage_manager.remove_metadata('Size', 'labels')
        storage_manager.remove_metadata('Size', 'locations')
        storage_manager.remove_metadata('Variance', 'locations')

        labels_metadata = {'Maximum': '', 'Mean': '', 'Minimum': ''}
        storage_manager.set_metadata(labels_metadata, 'labels')

        storage_manager = _bytes_ds_to_string_ds(storage_manager, 'labels')

        datasets = ['labels', 'locations']

        if 'MEG' in class_name:
            storage_manager.remove_metadata('Size', 'orientations')
            storage_manager.remove_metadata('Variance', 'orientations')
            datasets.append('orientations')

        _migrate_dataset_metadata(datasets, storage_manager)
        view_model_class = SensorsImporterModel
    elif 'Projection' in class_name:
        root_metadata['written_by'] = "tvb.adapters.datatypes.h5.projections_h5.ProjectionMatrixH5"
        root_metadata['projection_type'] = root_metadata["projection_type"].replace("\"", '')
        root_metadata['sensors'] = "urn:uuid:" + root_metadata['sensors']
        root_metadata['sources'] = "urn:uuid:" + root_metadata['sources']

        storage_manager.remove_metadata('Size', 'projection_data')
        storage_manager.remove_metadata('Variance', 'projection_data')

        _migrate_dataset_metadata(['projection_data'], storage_manager)
        view_model_class = ProjectionMatrixImporterModel

    elif class_name == 'LocalConnectivity':
        changed_values['surface'] = root_metadata['surface']
        root_metadata['cutoff'] = float(root_metadata['cutoff'])
        root_metadata['surface'] = "urn:uuid:" + root_metadata['surface']

        storage_manager.remove_metadata('shape', 'matrix')

        matrix_metadata = storage_manager.get_metadata('matrix')
        matrix_metadata['Shape'] = str(matrix_metadata['Shape'], 'utf-8')
        matrix_metadata['dtype'] = str(matrix_metadata['dtype'], 'utf-8')
        matrix_metadata['format'] = str(matrix_metadata['format'], 'utf-8')
        storage_manager.set_metadata(matrix_metadata, 'matrix')

        view_model_class = LocalConnectivityCreatorModel
        dependent_attributes['surface'] = root_metadata['surface']
    elif class_name == 'TimeSeriesRegion':
        root_metadata.pop(FIELD_SURFACE_MAPPING)
        root_metadata.pop(FIELD_VOLUME_MAPPING)

        root_metadata['nr_dimensions'] = int(root_metadata['nr_dimensions'])
        root_metadata['sample_period'] = float(root_metadata['sample_period'])
        root_metadata['start_time'] = float(root_metadata['start_time'])

        root_metadata["sample_period_unit"] = root_metadata["sample_period_unit"].replace("\"", '')
        root_metadata[DataTypeMetaData.KEY_TITLE] = root_metadata[DataTypeMetaData.KEY_TITLE].replace("\"", '')
        root_metadata['region_mapping'] = "urn:uuid:" + root_metadata['region_mapping']
        root_metadata['connectivity'] = "urn:uuid:" + root_metadata['connectivity']
        root_metadata = _pop_lengths(root_metadata)

        dependent_attributes['connectivity'] = root_metadata['connectivity']
        dependent_attributes['region_mapping'] = root_metadata['region_mapping']
        view_model_class = SimulatorAdapterModel

    elif 'Volume' in class_name:
        root_metadata['voxel_unit'] = root_metadata['voxel_unit'].replace("\"", '')

    if class_name == 'CoherenceSpectrum':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['nfft'] = int(root_metadata['nfft'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        array_data = storage_manager.get_data('array_data')
        storage_manager.remove_data('array_data')
        storage_manager.store_data('array_data', numpy.asarray(array_data, dtype=numpy.float64))

        _migrate_dataset_metadata(['array_data', 'frequency'], storage_manager)
        view_model_class = NodeCoherenceModel
        dependent_attributes['source'] = root_metadata['source']

    if  class_name == 'ComplexCoherenceSpectrum':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['epoch_length'] = float(root_metadata['epoch_length'])
        root_metadata['segment_length'] = float(root_metadata['segment_length'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        root_metadata['windowing_function'] = root_metadata['windowing_function'].replace("\"", '')
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['array_data', 'cross_spectrum'], storage_manager)
        view_model_class = NodeComplexCoherenceModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'WaveletCoefficients':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['q_ratio'] = float(root_metadata['q_ratio'])
        root_metadata['sample_period'] = float(root_metadata['sample_period'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        root_metadata['mother'] = root_metadata['mother'].replace("\"", '')
        root_metadata['normalisation'] = root_metadata['normalisation'].replace("\"", '')

        _migrate_dataset_metadata(['amplitude', 'array_data', 'frequencies', 'phase', 'power'], storage_manager)
        view_model_class = WaveletSpectrogramVisualizerModel

    if class_name == 'CrossCorrelation':
        changed_values['datatype'] = root_metadata['source']
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']
        _migrate_dataset_metadata(['array_data', 'time'], storage_manager)
        view_model_class = CrossCorrelationVisualizerModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'Fcd':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['sp'] = float(root_metadata['sp'])
        root_metadata['sw'] = float(root_metadata['sw'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        view_model_class = FCDAdapterModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'ConnectivityMeasure':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        _pop_lengths(root_metadata)

        root_metadata['source'] = "urn:uuid:" + root_metadata['source']
        root_metadata['connectivity'] = "urn:uuid:" + root_metadata['connectivity']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        view_model_class = ConnectivityMeasureImporterModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'FourierSpectrum':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['segment_length'] = float(root_metadata['segment_length'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['amplitude', 'array_data', 'average_power',
                                   'normalised_average_power', 'phase', 'power'], storage_manager)
        view_model_class = FourierSpectrumModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'IndependentComponents':
        root_metadata['n_components'] = int(root_metadata['n_components'])
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['component_time_series', 'mixing_matrix', 'norm_source',
                                   'normalised_component_time_series', 'prewhitening_matrix',
                                   'unmixing_matrix'], storage_manager)
        view_model_class = ICAAdapterModel

    if class_name == 'CorrelationCoefficients':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        view_model_class = CrossCorrelationVisualizerModel

    if class_name == 'PrincipalComponents':
        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['component_time_series', 'fractions',
                                   'norm_source', 'normalised_component_time_series',
                                   'weights'], storage_manager)
        view_model_class = PCAAdapterModel

    if class_name == 'Covariance':
        root_metadata.pop('aggregation_functions')
        root_metadata.pop('dimensions_labels')
        root_metadata.pop('nr_dimensions')
        root_metadata.pop('label_x')
        root_metadata.pop('label_y')
        root_metadata.pop(DataTypeMetaData.KEY_TITLE)
        _pop_lengths(root_metadata)

        root_metadata['source'] = "urn:uuid:" + root_metadata['source']

        _migrate_dataset_metadata(['array_data'], storage_manager)
        view_model_class = NodeCovarianceAdapterModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'DatatypeMeasure':
        root_metadata['written_by'] = 'tvb.core.entities.file.simulator.datatype_measure_h5.DatatypeMeasureH5'
        view_model_class = TimeseriesMetricsAdapterModel
        dependent_attributes['source'] = root_metadata['source']

    if class_name == 'StimuliRegion':
        root_metadata['connectivity'] = "urn:uuid:" + root_metadata['connectivity']

        _migrate_stimuli(root_metadata, storage_manager, ['weight'])
        view_model_class = RegionStimulusCreatorModel

    if class_name == 'StimuliSurface':
        root_metadata['surface'] = "urn:uuid:" + root_metadata['surface']

        _migrate_stimuli(root_metadata, storage_manager, ['focal_points_surface', 'focal_points_triangles'])
        view_model_class = SurfaceStimulusCreatorModel

    if class_name == 'ConnectivityAnnotations':
        root_metadata['connectivity'] = "urn:uuid:" + root_metadata['connectivity']
        root_metadata['written_by'] = "tvb.adapters.datatypes.h5.annotation_h5.ConnectivityAnnotationsH5"
        h5_class = ConnectivityAnnotationsH5

        _migrate_dataset_metadata(['region_annotations'], storage_manager)
        dependent_attributes['connectivity'] = root_metadata['connectivity']
        view_model_class = BRCOImporterModel

    root_metadata['operation_tag'] = ''
    storage_manager.set_metadata(root_metadata)

    if class_name in REBUILDABLE_TABLES:
        with h5_class(input_file) as f:
            datatype = REGISTRY.get_datatype_for_h5file(f)()
            f.load_into(datatype)
            generic_attributes = f.load_generic_attributes()
            datatype_index = REGISTRY.get_index_for_datatype(datatype.__class__)()

            for attr_name, attr_value in dependent_attributes.items():
                dependent_datatype_index = dao.get_datatype_by_gid(attr_value.replace('-', '').replace('urn:uuid:', ''))
                dependent_datatype = h5.load_from_index(dependent_datatype_index)
                setattr(datatype, attr_name, dependent_datatype)

            files_in_op_dir = os.listdir(os.path.join(input_file, os.pardir))
            has_vm = False
            if len(files_in_op_dir) > 2:
                for file in files_in_op_dir:
                    if view_model_class.__name__ in file:
                        has_vm = True
                        break

            op_id = input_file.split('\\')[-2]
            if has_vm is False:
                view_model = view_model_class()
                view_model.generic_attributes = generic_attributes

                operation = dao.get_operation_by_id(int(op_id))
                vm_attributes = [i for i in view_model_class.__dict__.keys() if i[:1] != '_']
                op_parameters = eval(operation.view_model_gid)

                # Check if datatype is a TimeSeries
                if 'parent_burst_id' in op_parameters:
                    burst_config = BurstConfiguration(operation.fk_launched_in)
                    dao.store_entity(burst_config)
                    generic_attributes.parent_burst = burst_config.gid
                    root_metadata['parent_burst'] = "urn:uuid:" + burst_config.gid
                    storage_manager.set_metadata(root_metadata)

                if 'time_series' in op_parameters:
                    ts = dao.get_datatype_by_gid(op_parameters['time_series'].replace('-', '').replace('urn:uuid:', ''))
                    root_metadata['parent_burst'] = "urn:uuid:" + ts.fk_parent_burst
                    storage_manager.set_metadata(root_metadata)

                for attr in vm_attributes:
                    if attr not in changed_values:
                        if attr in op_parameters:
                            try:
                                setattr(view_model, attr, op_parameters[attr])
                            except (TraitTypeError, TraitAttributeError):
                                pass
                    else:
                        setattr(view_model, attr, changed_values[attr])

                h5.store_view_model(view_model, os.path.dirname(input_file))

                operation.view_model_gid = view_model.gid.hex
                dao.store_entity(operation)

            datatype_index.fill_from_has_traits(datatype)
            datatype_index.fill_from_generic_attributes(generic_attributes)
            datatype_index.fk_from_operation = op_id

        dao.store_entity(datatype_index)
