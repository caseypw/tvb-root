# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2017, Baycrest Centre for Geriatric Care ("Baycrest") and others
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

from tvb.datatypes.connectivity import Connectivity
from tvb.datatypes.fcd import Fcd
from tvb.datatypes.graph import ConnectivityMeasure, CorrelationCoefficients, Covariance
from tvb.datatypes.local_connectivity import LocalConnectivity
from tvb.datatypes.mode_decompositions import PrincipalComponents, IndependentComponents
from tvb.datatypes.patterns import StimuliRegion, StimuliSurface
from tvb.datatypes.projections import ProjectionMatrix
from tvb.datatypes.region_mapping import RegionVolumeMapping, RegionMapping
from tvb.datatypes.sensors import Sensors
from tvb.adapters.datatypes.simulation_state import SimulationState
from tvb.datatypes.spectral import CoherenceSpectrum, ComplexCoherenceSpectrum, FourierSpectrum, WaveletCoefficients
from tvb.datatypes.structural import StructuralMRI
from tvb.datatypes.surfaces import Surface
from tvb.datatypes.temporal_correlations import CrossCorrelation
from tvb.datatypes.time_series import TimeSeries, TimeSeriesRegion, TimeSeriesSurface, TimeSeriesVolume
from tvb.datatypes.time_series import TimeSeriesEEG, TimeSeriesMEG, TimeSeriesSEEG
from tvb.datatypes.tracts import Tracts
from tvb.datatypes.volumes import Volume
from tvb.datatypes.cortex import Cortex
from tvb.core.entities.file.simulator.cortex_h5 import CortexH5
from tvb.core.entities.file.datatypes.annotation_h5 import ConnectivityAnnotationsH5, ConnectivityAnnotations
from tvb.core.entities.file.datatypes.connectivity_h5 import ConnectivityH5
from tvb.core.entities.file.datatypes.fcd_h5 import FcdH5
from tvb.core.entities.file.datatypes.graph_h5 import ConnectivityMeasureH5, CorrelationCoefficientsH5, CovarianceH5
from tvb.core.entities.file.datatypes.local_connectivity_h5 import LocalConnectivityH5
from tvb.core.entities.file.datatypes.mapped_value_h5 import DatatypeMeasureH5, ValueWrapperH5
from tvb.core.entities.file.datatypes.mode_decompositions_h5 import PrincipalComponentsH5, IndependentComponentsH5
from tvb.core.entities.file.datatypes.patterns_h5 import StimuliRegionH5, StimuliSurfaceH5
from tvb.core.entities.file.datatypes.projections_h5 import ProjectionMatrixH5
from tvb.core.entities.file.datatypes.region_mapping_h5 import RegionMappingH5, RegionVolumeMappingH5
from tvb.core.entities.file.datatypes.sensors_h5 import SensorsH5
from tvb.core.entities.file.datatypes.simulation_state_h5 import SimulationStateH5
from tvb.core.entities.file.datatypes.spectral_h5 import CoherenceSpectrumH5, ComplexCoherenceSpectrumH5
from tvb.core.entities.file.datatypes.spectral_h5 import FourierSpectrumH5, WaveletCoefficientsH5
from tvb.core.entities.file.datatypes.structural_h5 import StructuralMRIH5
from tvb.core.entities.file.datatypes.surface_h5 import SurfaceH5
from tvb.core.entities.file.datatypes.temporal_correlations_h5 import CrossCorrelationH5
from tvb.core.entities.file.datatypes.time_series_h5 import TimeSeriesH5, TimeSeriesRegionH5, TimeSeriesSurfaceH5
from tvb.core.entities.file.datatypes.time_series_h5 import TimeSeriesVolumeH5, TimeSeriesEEGH5, TimeSeriesMEGH5
from tvb.core.entities.file.datatypes.time_series_h5 import TimeSeriesSEEGH5
from tvb.core.entities.file.datatypes.tracts_h5 import TractsH5
from tvb.core.entities.file.datatypes.volumes_h5 import VolumeH5
from tvb.core.entities.model.datatypes.annotation import ConnectivityAnnotationsIndex
from tvb.core.entities.model.datatypes.connectivity import ConnectivityIndex
from tvb.core.entities.model.datatypes.fcd import FcdIndex
from tvb.core.entities.model.datatypes.graph import ConnectivityMeasureIndex, CorrelationCoefficientsIndex
from tvb.core.entities.model.datatypes.graph import CovarianceIndex
from tvb.core.entities.model.datatypes.local_connectivity import LocalConnectivityIndex
from tvb.core.entities.model.datatypes.mapped_value import DatatypeMeasureIndex, ValueWrapperIndex
from tvb.core.entities.model.datatypes.mode_decompositions import PrincipalComponentsIndex, IndependentComponentsIndex
from tvb.core.entities.model.datatypes.patterns import StimuliRegionIndex, StimuliSurfaceIndex
from tvb.core.entities.model.datatypes.projections import ProjectionMatrixIndex
from tvb.core.entities.model.datatypes.region_mapping import RegionVolumeMappingIndex, RegionMappingIndex
from tvb.core.entities.model.datatypes.sensors import SensorsIndex
from tvb.core.entities.model.datatypes.simulation_state import SimulationStateIndex
from tvb.core.entities.model.datatypes.spectral import CoherenceSpectrumIndex, ComplexCoherenceSpectrumIndex
from tvb.core.entities.model.datatypes.spectral import FourierSpectrumIndex, WaveletCoefficientsIndex
from tvb.core.entities.model.datatypes.structural import StructuralMRIIndex
from tvb.core.entities.model.datatypes.surface import SurfaceIndex
from tvb.core.entities.model.datatypes.temporal_correlations import CrossCorrelationIndex
from tvb.core.entities.model.datatypes.time_series import TimeSeriesIndex, TimeSeriesRegionIndex, TimeSeriesSurfaceIndex
from tvb.core.entities.model.datatypes.time_series import TimeSeriesVolumeIndex, TimeSeriesEEGIndex, TimeSeriesMEGIndex
from tvb.core.entities.model.datatypes.time_series import TimeSeriesSEEGIndex
from tvb.core.entities.model.datatypes.tracts import TractsIndex
from tvb.core.entities.model.datatypes.volume import VolumeIndex

from tvb.core.neocom.h5 import REGISTRY


# an alternative approach is to make each h5file declare if it has a corresponding datatype
# then in a metaclass hook each class creation and populate a map
def populate_datatypes_registry():
    REGISTRY.register_datatype(Connectivity, ConnectivityH5, ConnectivityIndex)
    REGISTRY.register_datatype(LocalConnectivity, LocalConnectivityH5, LocalConnectivityIndex)
    REGISTRY.register_datatype(ProjectionMatrix, ProjectionMatrixH5, ProjectionMatrixIndex)
    REGISTRY.register_datatype(RegionVolumeMapping, RegionVolumeMappingH5, RegionVolumeMappingIndex)
    REGISTRY.register_datatype(RegionMapping, RegionMappingH5, RegionMappingIndex)
    REGISTRY.register_datatype(Sensors, SensorsH5, SensorsIndex)
    REGISTRY.register_datatype(SimulationState, SimulationStateH5, SimulationStateIndex)
    REGISTRY.register_datatype(CoherenceSpectrum, CoherenceSpectrumH5, CoherenceSpectrumIndex)
    REGISTRY.register_datatype(ComplexCoherenceSpectrum, ComplexCoherenceSpectrumH5, ComplexCoherenceSpectrumIndex)
    REGISTRY.register_datatype(FourierSpectrum, FourierSpectrumH5, FourierSpectrumIndex)
    REGISTRY.register_datatype(WaveletCoefficients, WaveletCoefficientsH5, WaveletCoefficientsIndex)
    REGISTRY.register_datatype(StructuralMRI, StructuralMRIH5, StructuralMRIIndex)
    REGISTRY.register_datatype(Surface, SurfaceH5, SurfaceIndex)
    REGISTRY.register_datatype(CrossCorrelation, CrossCorrelationH5, CrossCorrelationIndex)
    REGISTRY.register_datatype(TimeSeries, TimeSeriesH5, TimeSeriesIndex)
    REGISTRY.register_datatype(TimeSeriesRegion, TimeSeriesRegionH5, TimeSeriesRegionIndex)
    REGISTRY.register_datatype(TimeSeriesSurface, TimeSeriesSurfaceH5, TimeSeriesSurfaceIndex)
    REGISTRY.register_datatype(TimeSeriesVolume, TimeSeriesVolumeH5, TimeSeriesVolumeIndex)
    REGISTRY.register_datatype(TimeSeriesEEG, TimeSeriesEEGH5, TimeSeriesEEGIndex)
    REGISTRY.register_datatype(TimeSeriesMEG, TimeSeriesMEGH5, TimeSeriesMEGIndex)
    REGISTRY.register_datatype(TimeSeriesSEEG, TimeSeriesSEEGH5, TimeSeriesSEEGIndex)
    REGISTRY.register_datatype(Tracts, TractsH5, TractsIndex)
    REGISTRY.register_datatype(Volume, VolumeH5, VolumeIndex)
    REGISTRY.register_datatype(PrincipalComponents, PrincipalComponentsH5, PrincipalComponentsIndex)
    REGISTRY.register_datatype(IndependentComponents, IndependentComponentsH5, IndependentComponentsIndex)
    REGISTRY.register_datatype(ConnectivityMeasure, ConnectivityMeasureH5, ConnectivityMeasureIndex)
    REGISTRY.register_datatype(CorrelationCoefficients, CorrelationCoefficientsH5, CorrelationCoefficientsIndex)
    REGISTRY.register_datatype(Covariance, CovarianceH5, CovarianceIndex)
    REGISTRY.register_datatype(Fcd, FcdH5, FcdIndex)
    REGISTRY.register_datatype(StimuliRegion, StimuliRegionH5, StimuliRegionIndex)
    REGISTRY.register_datatype(StimuliSurface, StimuliSurfaceH5, StimuliSurfaceIndex)
    REGISTRY.register_datatype(None, DatatypeMeasureH5, DatatypeMeasureIndex)
    REGISTRY.register_datatype(ConnectivityAnnotations, ConnectivityAnnotationsH5, ConnectivityAnnotationsIndex)
    REGISTRY.register_datatype(None, ValueWrapperH5, ValueWrapperIndex)
    REGISTRY.register_datatype(Cortex, CortexH5, None)