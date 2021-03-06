##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2019, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################
"""
Tests for ControlVolumeBlockData.

Author: Andrew Lee
"""
import pytest
from pyomo.environ import ConcreteModel, Constraint, Expression, Set, Var
from pyomo.dae import ContinuousSet, DerivativeVar
from pyomo.common.config import ConfigBlock
from pyomo.core.base.constraint import _GeneralConstraintData
from idaes.core import (ControlVolume1DBlock,
                        FlowsheetBlockData,
                        declare_process_block_class,
                        FlowDirection,
                        PhysicalParameterBlock,
                        StateBlock,
                        StateBlockData,
                        ReactionParameterBlock,
                        ReactionBlockBase,
                        ReactionBlockDataBase,
                        MaterialFlowBasis)
from idaes.core.control_volume1d import ControlVolume1DBlockData
from idaes.core.util.exceptions import (BalanceTypeNotSupportedError,
                                        ConfigurationError,
                                        PropertyNotSupportedError)
from idaes.core.control_volume1d import DistributedVars


# -----------------------------------------------------------------------------
# Mockup classes for testing
@declare_process_block_class("Flowsheet")
class _Flowsheet(FlowsheetBlockData):
    def build(self):
        super(_Flowsheet, self).build()


@declare_process_block_class("PhysicalParameterTestBlock")
class _PhysicalParameterBlock(PhysicalParameterBlock):
    def build(self):
        super(_PhysicalParameterBlock, self).build()

        self.phase_list = Set(initialize=["p1", "p2"])
        self.component_list = Set(initialize=["c1", "c2"])
        self.phase_equilibrium_idx = Set(initialize=["e1", "e2"])
        self.element_list = Set(initialize=["H", "He", "Li"])
        self.element_comp = {"c1": {"H": 1, "He": 2, "Li": 3},
                             "c2": {"H": 4, "He": 5, "Li": 6}}

        self.phase_equilibrium_list = \
            {"e1": ["c1", ("p1", "p2")],
             "e2": ["c2", ("p1", "p2")]}

        # Attribute to switch flow basis for testing
        self.basis_switch = 1

        self.state_block_class = TestStateBlock

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({'time': 's',
                               'length': 'm',
                               'mass': 'g',
                               'amount': 'mol',
                               'temperature': 'K',
                               'energy': 'J',
                               'holdup': 'mol'})


class SBlockBase(StateBlock):
    def initialize(blk, outlvl=0, optarg=None, solver=None,
                   hold_state=False, **state_args):
        for k in blk.keys():
            blk[k].init_test = True

@declare_process_block_class("TestStateBlock", block_class=SBlockBase)
class StateTestBlockData(StateBlockData):
    CONFIG = ConfigBlock(implicit=True)

    def build(self):
        super(StateTestBlockData, self).build()

        self.test_var = Var()
        self.pressure = Var()

    def get_material_flow_terms(b, p, j):
        return b.test_var

    def get_material_density_terms(b, p, j):
        return b.test_var

    def get_enthalpy_flow_terms(b, p):
        return b.test_var

    def get_enthalpy_density_terms(b, p):
        return b.test_var

    def define_state_vars(b):
        """Define state variables for ports."""
        return {}

    def model_check(self):
        self.check = True

    def get_material_flow_basis(b):
        if b.config.parameters.basis_switch == 1:
            return MaterialFlowBasis.molar
        elif b.config.parameters.basis_switch == 2:
            return MaterialFlowBasis.mass
        else:
            return MaterialFlowBasis.other


@declare_process_block_class("ReactionParameterTestBlock")
class _ReactionParameterBlock(ReactionParameterBlock):
    def build(self):
        super(_ReactionParameterBlock, self).build()

        self.phase_list = Set(initialize=["p1", "p2"])
        self.component_list = Set(initialize=["c1", "c2"])
        self.rate_reaction_idx = Set(initialize=["r1", "r2"])
        self.equilibrium_reaction_idx = Set(initialize=["e1", "e2"])

        self.rate_reaction_stoichiometry = {("r1", "p1", "c1"): 1,
                                            ("r1", "p1", "c2"): 1,
                                            ("r1", "p2", "c1"): 1,
                                            ("r1", "p2", "c2"): 1,
                                            ("r2", "p1", "c1"): 1,
                                            ("r2", "p1", "c2"): 1,
                                            ("r2", "p2", "c1"): 1,
                                            ("r2", "p2", "c2"): 1}
        self.equilibrium_reaction_stoichiometry = {
                                            ("e1", "p1", "c1"): 1,
                                            ("e1", "p1", "c2"): 1,
                                            ("e1", "p2", "c1"): 1,
                                            ("e1", "p2", "c2"): 1,
                                            ("e2", "p1", "c1"): 1,
                                            ("e2", "p1", "c2"): 1,
                                            ("e2", "p2", "c1"): 1,
                                            ("e2", "p2", "c2"): 1}

        self.reaction_block_class = ReactionBlock

        # Attribute to switch flow basis for testing
        self.basis_switch = 1

    @classmethod
    def define_metadata(cls, obj):
        obj.add_default_units({'time': 's',
                               'length': 'm',
                               'mass': 'g',
                               'amount': 'mol',
                               'temperature': 'K',
                               'energy': 'J',
                               'holdup': 'mol'})

    @classmethod
    def get_required_properties(self):
        return {}


class RBlockBase(ReactionBlockBase):
    def initialize(blk, outlvl=0, optarg=None, solver=None):
        for k in blk.keys():
            blk[k].init_test = True


@declare_process_block_class("ReactionBlock", block_class=RBlockBase)
class ReactionBlockData(ReactionBlockDataBase):
    CONFIG = ConfigBlock(implicit=True)

    def build(self):
        super(ReactionBlockData, self).build()

        self.reaction_rate = Var(["r1", "r2"])

        self.dh_rxn = {"r1": 1,
                       "r2": 2,
                       "e1": 3,
                       "e2": 4}

    def model_check(self):
        self.check = True

    def get_reaction_rate_basis(b):
        if b.config.parameters.basis_switch == 1:
            return MaterialFlowBasis.molar
        elif b.config.parameters.basis_switch == 2:
            return MaterialFlowBasis.mass
        else:
            return MaterialFlowBasis.other


@declare_process_block_class("CVFrame")
class CVFrameData(ControlVolume1DBlockData):
    def build(self):
        super(ControlVolume1DBlockData, self).build()


# -----------------------------------------------------------------------------
# Test DistributedVars Enum
def test_DistributedVars():
    assert len(DistributedVars) == 2


# -----------------------------------------------------------------------------
# Basic tests
def test_base_build():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = CVFrame(default={"property_package": m.fs.pp})

    assert len(m.fs.cv.config) == 12
    assert m.fs.cv.config.dynamic is False
    assert m.fs.cv.config.has_holdup is False
    assert m.fs.cv.config.property_package == m.fs.pp
    assert isinstance(m.fs.cv.config.property_package_args, ConfigBlock)
    assert len(m.fs.cv.config.property_package_args) == 0
    assert m.fs.cv.config.reaction_package is None
    assert isinstance(m.fs.cv.config.reaction_package_args, ConfigBlock)
    assert len(m.fs.cv.config.reaction_package_args) == 0
    assert m.fs.cv.config.auto_construct is False
    assert m.fs.cv.config.area_definition == DistributedVars.uniform
    assert m.fs.cv.config.transformation_method is None
    assert m.fs.cv.config.transformation_scheme is None
    assert m.fs.cv.config.finite_elements is None
    assert m.fs.cv.config.collocation_points is None


def test_validate_config_args_transformation_method_none():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={"property_package": m.fs.pp})


def test_validate_config_args_transformation_scheme_none():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference"})


def test_validate_config_args_transformation_scheme_invalid_1():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "LAGRANGE-RADAU"})


def test_validate_config_args_transformation_scheme_invalid_2():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "LAGRANGE-LEGENDRE"})


def test_validate_config_args_transformation_scheme_invalid_3():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.collocation",
                "transformation_scheme": "BACKWARD"})


def test_validate_config_args_transformation_scheme_invalid_4():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    with pytest.raises(ConfigurationError):
        m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.collocation",
                "transformation_scheme": "FORWARD"})


# -----------------------------------------------------------------------------
# Test add_geometry
def test_add_geometry_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()

    assert isinstance(m.fs.cv.length_domain, ContinuousSet)
    assert len(m.fs.cv.length_domain) == 2
    assert isinstance(m.fs.cv.area, Var)
    assert len(m.fs.cv.area) == 1.0
    assert m.fs.cv.area.value == 1.0
    assert isinstance(m.fs.cv.length, Var)
    assert len(m.fs.cv.length) == 1.0
    assert m.fs.cv.length.value == 1.0
    assert m.fs.cv._flow_direction == FlowDirection.forward


def test_add_geometry_inherited_domain():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.domain = ContinuousSet(bounds=(0, 1))

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD"})

    m.fs.cv.add_geometry(length_domain=m.fs.domain)

    assert m.fs.cv.length_domain == m.fs.domain


def test_add_geometry_length_domain_set():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD"})

    m.fs.cv.add_geometry(length_domain_set=[0.0, 0.2, 0.7, 1.0])

    assert len(m.fs.cv.length_domain) == 4
    for p in m.fs.cv.length_domain:
        assert p in [0.0, 0.2, 0.7, 1.0]


def test_add_geometry_flow_direction():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD"})

    m.fs.cv.add_geometry(flow_direction=FlowDirection.backward)

    assert m.fs.cv._flow_direction == FlowDirection.backward


def test_add_geometry_flow_direction_invalid():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD"})

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_geometry(flow_direction="foo")


def test_add_geometry_discretized_area():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "area_definition": DistributedVars.variant})

    m.fs.cv.add_geometry()

    assert len(m.fs.cv.area) == 2


# -----------------------------------------------------------------------------
# Test apply_transformation
def test_apply_transformation_finite_elements_none():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD"})

    m.fs.cv.add_geometry()
    with pytest.raises(ConfigurationError):
        m.fs.cv.apply_transformation()


def test_apply_transformation_collocation_points_none():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.collocation",
                "transformation_scheme": "LAGRANGE-RADAU",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    with pytest.raises(ConfigurationError):
        m.fs.cv.apply_transformation()


def test_apply_transformation_BFD_10():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.apply_transformation()

    assert len(m.fs.cv.length_domain) == 11


def test_apply_transformation_FFD_12():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 12})

    m.fs.cv.add_geometry()
    m.fs.cv.apply_transformation()

    assert len(m.fs.cv.length_domain) == 13


def test_apply_transformation_Lagrange_Radau_8_3():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.collocation",
                "transformation_scheme": "LAGRANGE-RADAU",
                "finite_elements": 8,
                "collocation_points": 3})

    m.fs.cv.add_geometry()
    m.fs.cv.apply_transformation()

    assert len(m.fs.cv.length_domain) == 25


def test_apply_transformation_Lagrange_Legendre_3_7():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.collocation",
                "transformation_scheme": "LAGRANGE-LEGENDRE",
                "finite_elements": 9,
                "collocation_points": 4})

    m.fs.cv.add_geometry()
    m.fs.cv.apply_transformation()

    assert len(m.fs.cv.length_domain) == 46


def test_apply_transformation_external_domain():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})

    m.fs.cset = ContinuousSet(bounds=(0, 1))

    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry(length_domain=m.fs.cset)
    with pytest.raises(ConfigurationError):
        m.fs.cv.apply_transformation()


# -----------------------------------------------------------------------------
# Test add_state_blocks
def test_add_state_blocks():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    assert hasattr(m.fs.cv, "properties")
    assert len(m.fs.cv.properties) == 2

    for x in m.fs.cv.length_domain:
        assert len(m.fs.cv.properties[0, x].config) == 3
        if x == 0:
            assert m.fs.cv.properties[0, x].config.defined_state is True
        else:
            assert m.fs.cv.properties[0, x].config.defined_state is False
        assert m.fs.cv.properties[0, x].config.has_phase_equilibrium is False
        assert m.fs.cv.properties[0, x].config.parameters == m.fs.pp


def test_add_state_block_forward_flow():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(information_flow=FlowDirection.forward,
                             has_phase_equilibrium=False)

    assert m.fs.cv.properties[0, 0].config.defined_state is True
    assert m.fs.cv.properties[0, 1].config.defined_state is False


def test_add_state_block_backward_flow():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(information_flow=FlowDirection.backward,
                             has_phase_equilibrium=False)

    assert m.fs.cv.properties[0, 0].config.defined_state is False
    assert m.fs.cv.properties[0, 1].config.defined_state is True


def test_add_state_blocks_has_phase_equilibrium():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)

    for x in m.fs.cv.length_domain:
        assert m.fs.cv.properties[0, x].config.has_phase_equilibrium is True


def test_add_state_blocks_no_has_phase_equilibrium():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_state_blocks()


def test_add_state_blocks_custom_args():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "property_package_args": {"test": "test"}})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    for x in m.fs.cv.length_domain:
        assert len(m.fs.cv.properties[0, x].config) == 4
        assert m.fs.cv.properties[0, x].config.test == "test"


# -----------------------------------------------------------------------------
# Test add_reaction_blocks
def test_add_reaction_blocks():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    assert hasattr(m.fs.cv, "reactions")
    assert len(m.fs.cv.reactions) == 2
    assert len(m.fs.cv.reactions[0, 0].config) == 3
    assert m.fs.cv.reactions[0, 0].config.state_block == m.fs.cv.properties
    assert m.fs.cv.reactions[0, 0].state_ref == m.fs.cv.properties[0, 0]
    assert m.fs.cv.reactions[0, 0].config.has_equilibrium is False
    assert m.fs.cv.reactions[0, 0].config.parameters == m.fs.rp


def test_add_reaction_blocks_has_equilibrium():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)

    assert m.fs.cv.reactions[0, 0].config.has_equilibrium is True


def test_add_reaction_blocks_no_has_equilibrium():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_reaction_blocks()


def test_add_reaction_blocks_custom_args():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "reaction_package_args": {"test1": 1}})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    assert m.fs.cv.reactions[0, 0].config.test1 == 1


# -----------------------------------------------------------------------------
# Test _add_phase_fractions
def test_add_phase_fractions():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv._add_phase_fractions()

    assert isinstance(m.fs.cv.phase_fraction, Var)
    assert len(m.fs.cv.phase_fraction) == 4
    assert isinstance(m.fs.cv.sum_of_phase_fractions, Constraint)


def test_add_phase_fractions_single_phase():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.del_component(m.fs.pp.phase_list)
    m.fs.pp.phase_list = Set(initialize=["p1"])

    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv._add_phase_fractions()

    assert isinstance(m.fs.cv.phase_fraction, Expression)
    assert len(m.fs.cv.phase_fraction) == 2
    assert not hasattr(m.fs.cv, "sum_of_phase_fractions")


# -----------------------------------------------------------------------------
# Test reaction rate conversion method
def test_rxn_rate_conv_no_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                assert m.fs.cv._rxn_rate_conv(
                        t, x, j, has_rate_reactions=False) == 1


def test_rxn_rate_conv_property_basis_other():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                with pytest.raises(ConfigurationError):
                    m.fs.cv._rxn_rate_conv(t, x, j, has_rate_reactions=True)


def test_rxn_rate_conv_reaction_basis_other():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.rp.basis_switch = 3

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                with pytest.raises(ConfigurationError):
                    m.fs.cv._rxn_rate_conv(t, x, j, has_rate_reactions=True)


def test_rxn_rate_conv_both_molar():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                assert m.fs.cv._rxn_rate_conv(
                        t, x, j, has_rate_reactions=True) == 1


def test_rxn_rate_conv_both_mass():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.basis_switch = 2
    m.fs.rp.basis_switch = 2

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                assert m.fs.cv._rxn_rate_conv(
                        t, x, j, has_rate_reactions=True) == 1


def test_rxn_rate_conv_mole_mass_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.basis_switch = 1
    m.fs.rp.basis_switch = 2

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                with pytest.raises(PropertyNotSupportedError):
                    m.fs.cv._rxn_rate_conv(t, x, j, has_rate_reactions=True)


def test_rxn_rate_conv_mass_mole_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.basis_switch = 2
    m.fs.rp.basis_switch = 1

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            for j in m.fs.pp.component_list:
                with pytest.raises(PropertyNotSupportedError):
                    m.fs.cv._rxn_rate_conv(t, x, j, has_rate_reactions=True)


def test_rxn_rate_conv_mole_mass():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.basis_switch = 1
    m.fs.rp.basis_switch = 2

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = {"c1": 2, "c2": 3}
            for j in m.fs.pp.component_list:
                assert (m.fs.cv._rxn_rate_conv(
                        t, x, j, has_rate_reactions=True) ==
                        1/m.fs.cv.properties[t, x].mw[j])


def test_rxn_rate_conv_mass_mole():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.basis_switch = 2
    m.fs.rp.basis_switch = 1

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = {"c1": 2, "c2": 3}
            for j in m.fs.pp.component_list:
                assert (m.fs.cv._rxn_rate_conv(
                        t, x, j, has_rate_reactions=True) ==
                        m.fs.cv.properties[t, x].mw[j])


# -----------------------------------------------------------------------------
# Test add_phase_component_balances
def test_add_phase_component_balances_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    for p in m.fs.pp.phase_list:
        for j in m.fs.pp.component_list:
            with pytest.raises(KeyError):
                assert m.fs.cv.material_balances[0, 0, p, j]
            assert type(m.fs.cv.material_balances[0, 1, p, j]) is \
                _GeneralConstraintData


def test_add_phase_component_balances_default_FFD():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    for p in m.fs.pp.phase_list:
        for j in m.fs.pp.component_list:
            with pytest.raises(KeyError):
                assert m.fs.cv.material_balances[0, 1, p, j]
            assert type(m.fs.cv.material_balances[0, 0, p, j]) is \
                _GeneralConstraintData


def test_add_phase_component_balances_distrubuted_area():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "area_definition": DistributedVars.variant})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 4


def test_add_phase_component_balances_dynamic():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": True})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "dynamic": True})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 8
    assert isinstance(m.fs.cv.phase_fraction, Var)
    assert isinstance(m.fs.cv.material_holdup, Var)
    assert isinstance(m.fs.cv.material_accumulation, Var)


def test_add_phase_component_balances_rate_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances(has_rate_reactions=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    assert isinstance(m.fs.cv.rate_reaction_generation, Var)
    assert isinstance(m.fs.cv.rate_reaction_extent, Var)
    assert isinstance(m.fs.cv.rate_reaction_stoichiometry_constraint,
                      Constraint)


def test_add_phase_component_balances_rate_rxns_no_ReactionBlock():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(has_rate_reactions=True)


def test_add_phase_component_balances_rate_rxns_no_rxn_idx():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.rp.del_component(m.fs.rp.rate_reaction_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_phase_component_balances(has_rate_reactions=True)


def test_add_phase_component_balances_eq_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)

    mb = m.fs.cv.add_phase_component_balances(has_equilibrium_reactions=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    assert isinstance(m.fs.cv.equilibrium_reaction_generation, Var)
    assert isinstance(m.fs.cv.equilibrium_reaction_extent, Var)
    assert isinstance(m.fs.cv.equilibrium_reaction_stoichiometry_constraint,
                      Constraint)


def test_add_phase_component_balances_eq_rxns_not_active():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(has_equilibrium_reactions=True)


def test_add_phase_component_balances_eq_rxns_no_idx():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.rp.del_component(m.fs.rp.equilibrium_reaction_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_phase_component_balances(has_equilibrium_reactions=True)


def test_add_phase_component_balances_eq_rxns_no_ReactionBlock():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(has_equilibrium_reactions=True)


def test_add_phase_component_balances_phase_eq():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances(has_phase_equilibrium=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    assert isinstance(m.fs.cv.phase_equilibrium_generation, Var)


def test_add_phase_component_balances_phase_eq_not_active():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(has_phase_equilibrium=True)


def test_add_phase_component_balances_phase_eq_no_idx():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_phase_component_balances(has_phase_equilibrium=True)


def test_add_phase_component_balances_mass_transfer():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_phase_component_balances(has_mass_transfer=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    assert isinstance(m.fs.cv.mass_transfer_term, Var)


def test_add_phase_component_balances_custom_molar_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    mb = m.fs.cv.add_phase_component_balances(custom_molar_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4


def test_add_phase_component_balances_custom_molar_term_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_phase_component_balances(custom_molar_term=custom_method)


def test_add_phase_component_balances_custom_molar_term_mass_flow_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = Var(
                m.fs.cv.properties[t, x].config.parameters.component_list)

    mb = m.fs.cv.add_phase_component_balances(custom_molar_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4


def test_add_phase_component_balances_custom_molar_term_undefined_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(custom_molar_term=custom_method)


def test_add_phase_component_balances_custom_mass_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    mb = m.fs.cv.add_phase_component_balances(custom_mass_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4


def test_add_phase_component_balances_custom_mass_term_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 1
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_phase_component_balances(custom_mass_term=custom_method)


def test_add_phase_component_balances_custom_mass_term_mole_flow_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = Var(
                m.fs.cv.properties[t, x].config.parameters.component_list)

    mb = m.fs.cv.add_phase_component_balances(custom_mass_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 4


def test_add_phase_component_balances_custom_mass_term_undefined_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.phase_list,
                           m.fs.pp.component_list)

    def custom_method(t, x, p, j):
        return m.fs.cv.test_var[t, p, j]

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_phase_component_balances(custom_mass_term=custom_method)


# -----------------------------------------------------------------------------
# Test add_total_component_balances
def test_add_total_component_balances_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 2

    for j in m.fs.pp.component_list:
        with pytest.raises(KeyError):
            assert m.fs.cv.material_balances[0, 0, j]
        assert type(m.fs.cv.material_balances[0, 1, j]) is \
            _GeneralConstraintData


def test_add_total_component_balances_default_FFD():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 2

    for j in m.fs.pp.component_list:
        with pytest.raises(KeyError):
            assert m.fs.cv.material_balances[0, 1, j]
        assert type(m.fs.cv.material_balances[0, 0, j]) is \
            _GeneralConstraintData


def test_add_total_component_balances_distrubuted_area():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "area_definition": DistributedVars.variant})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 2


def test_add_total_component_balances_dynamic():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": True})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "dynamic": True})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 4
    assert isinstance(m.fs.cv.phase_fraction, Var)
    assert isinstance(m.fs.cv.material_holdup, Var)
    assert isinstance(m.fs.cv.material_accumulation, Var)


def test_add_total_component_balances_rate_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances(has_rate_reactions=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2
    assert isinstance(m.fs.cv.rate_reaction_generation, Var)
    assert isinstance(m.fs.cv.rate_reaction_extent, Var)
    assert isinstance(m.fs.cv.rate_reaction_stoichiometry_constraint,
                      Constraint)


def test_add_total_component_balances_rate_rxns_no_ReactionBlock():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(has_rate_reactions=True)


def test_add_total_component_balances_rate_rxns_no_rxn_idx():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.rp.del_component(m.fs.rp.rate_reaction_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_total_component_balances(has_rate_reactions=True)


def test_add_total_component_balances_eq_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)

    mb = m.fs.cv.add_total_component_balances(has_equilibrium_reactions=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2
    assert isinstance(m.fs.cv.equilibrium_reaction_generation, Var)
    assert isinstance(m.fs.cv.equilibrium_reaction_extent, Var)
    assert isinstance(m.fs.cv.equilibrium_reaction_stoichiometry_constraint,
                      Constraint)


def test_add_total_component_balances_eq_rxns_not_active():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(has_equilibrium_reactions=True)


def test_add_total_component_balances_eq_rxns_no_idx():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.rp.del_component(m.fs.rp.equilibrium_reaction_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_total_component_balances(has_equilibrium_reactions=True)


def test_add_total_component_balances_eq_rxns_no_ReactionBlock():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(has_equilibrium_reactions=True)


def test_add_total_component_balances_phase_eq_not_active():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(has_phase_equilibrium=True)


def test_add_total_component_balances_mass_transfer():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_component_balances(has_mass_transfer=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2
    assert isinstance(m.fs.cv.mass_transfer_term, Var)


def test_add_total_component_balances_custom_molar_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    mb = m.fs.cv.add_total_component_balances(custom_molar_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2


def test_add_total_component_balances_custom_molar_term_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_total_component_balances(custom_molar_term=custom_method)


def test_add_total_component_balances_custom_molar_term_mass_flow_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = Var(
                m.fs.cv.properties[t, x].config.parameters.component_list)

    mb = m.fs.cv.add_total_component_balances(custom_molar_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2


def test_add_total_component_balances_custom_molar_term_undefined_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(custom_molar_term=custom_method)


def test_add_total_component_balances_custom_mass_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    mb = m.fs.cv.add_total_component_balances(custom_mass_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2


def test_add_total_component_balances_custom_mass_term_no_mw():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 1
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_total_component_balances(custom_mass_term=custom_method)


def test_add_total_component_balances_custom_mass_term_mole_flow_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 2
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            m.fs.cv.properties[t, x].mw = Var(
                m.fs.cv.properties[t, x].config.parameters.component_list)

    mb = m.fs.cv.add_total_component_balances(custom_mass_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 2


def test_add_total_component_balances_custom_mass_term_undefined_basis():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.pp.basis_switch = 3
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.component_list)

    def custom_method(t, x, j):
        return m.fs.cv.test_var[t, j]

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_component_balances(custom_mass_term=custom_method)


# -----------------------------------------------------------------------------
# Test add_total_element_balances
def test_add_total_element_balances_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_element_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 3

    for j in m.fs.pp.element_list:
        with pytest.raises(KeyError):
            assert m.fs.cv.element_balances[0, 0, j]
        assert type(m.fs.cv.element_balances[0, 1, j]) is \
            _GeneralConstraintData


def test_add_total_element_balances_default_FFD():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_element_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 3

    for j in m.fs.pp.element_list:
        with pytest.raises(KeyError):
            assert m.fs.cv.element_balances[0, 1, j]
        assert type(m.fs.cv.element_balances[0, 0, j]) is \
            _GeneralConstraintData


def test_add_total_element_balances_distrubuted_area():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "area_definition": DistributedVars.variant})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_element_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 3


def test_add_total_element_balances_properties_not_supported():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.element_list)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(PropertyNotSupportedError):
        m.fs.cv.add_total_element_balances()


def test_add_total_element_balances_dynamic():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": True})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "dynamic": True})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_element_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 6
    assert isinstance(m.fs.cv.phase_fraction, Var)
    assert isinstance(m.fs.cv.element_holdup, Var)
    assert isinstance(m.fs.cv.element_accumulation, Var)


def test_add_total_element_balances_rate_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_element_balances(has_rate_reactions=True)


def test_add_total_element_balances_eq_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_element_balances(has_equilibrium_reactions=True)


def test_add_total_element_balances_phase_eq():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_element_balances(has_phase_equilibrium=True)


def test_add_total_element_balances_mass_transfer():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_element_balances(has_mass_transfer=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 3
    assert isinstance(m.fs.cv.elemental_mass_transfer_term, Var)


def test_add_total_element_balances_custom_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time,
                           m.fs.pp.element_list)

    def custom_method(t, x, e):
        return m.fs.cv.test_var[t, e]

    mb = m.fs.cv.add_total_element_balances(
            custom_elemental_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 3


# -----------------------------------------------------------------------------
# Test unsupported material balance types
def test_add_total_material_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_total_material_balances()


# -----------------------------------------------------------------------------
# Test phase enthalpy balances
def test_add_total_enthalpy_balances_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    eb = m.fs.cv.add_total_enthalpy_balances()

    assert isinstance(eb, Constraint)
    assert len(eb) == 1
    assert isinstance(m.fs.cv._enthalpy_flow, Var)
    assert isinstance(m.fs.cv.enthalpy_flow_linking_constraint, Constraint)
    assert isinstance(m.fs.cv.enthalpy_flow_dx, DerivativeVar)

    with pytest.raises(KeyError):
        assert m.fs.cv.enthalpy_balances[0, 0]
    assert type(m.fs.cv.enthalpy_balances[0, 1]) is \
        _GeneralConstraintData


def test_add_total_enthalpy_balances_default_FFD():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    eb = m.fs.cv.add_total_enthalpy_balances()

    assert isinstance(eb, Constraint)
    assert len(eb) == 1
    assert isinstance(m.fs.cv._enthalpy_flow, Var)
    assert isinstance(m.fs.cv.enthalpy_flow_linking_constraint, Constraint)
    assert isinstance(m.fs.cv.enthalpy_flow_dx, DerivativeVar)

    with pytest.raises(KeyError):
        assert m.fs.cv.enthalpy_balances[0, 1]
    assert type(m.fs.cv.enthalpy_balances[0, 0]) is \
        _GeneralConstraintData


def test_add_total_enthalpy_balances_distributed_area():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "area_definition": DistributedVars.variant})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    eb = m.fs.cv.add_total_enthalpy_balances()

    assert isinstance(eb, Constraint)
    assert len(eb) == 1
    assert isinstance(m.fs.cv._enthalpy_flow, Var)
    assert isinstance(m.fs.cv.enthalpy_flow_linking_constraint, Constraint)
    assert isinstance(m.fs.cv.enthalpy_flow_dx, DerivativeVar)


def test_add_total_enthalpy_balances_dynamic():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": True})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10,
                "dynamic": True})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_enthalpy_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 2
    assert isinstance(m.fs.cv.phase_fraction, Var)
    assert isinstance(m.fs.cv.enthalpy_holdup, Var)
    assert isinstance(m.fs.cv.enthalpy_accumulation, Var)


def test_add_total_enthalpy_balances_heat_transfer():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_enthalpy_balances(has_heat_transfer=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 1
    assert isinstance(m.fs.cv.heat, Var)


def test_add_total_enthalpy_balances_work_transfer():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_enthalpy_balances(has_work_transfer=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 1
    assert isinstance(m.fs.cv.work, Var)


def test_add_total_enthalpy_balances_custom_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time)

    def custom_method(t, x):
        return m.fs.cv.test_var[t]

    mb = m.fs.cv.add_total_enthalpy_balances(custom_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 1


def test_add_total_enthalpy_balances_dh_rxn_no_extents():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(ConfigurationError):
        m.fs.cv.add_total_enthalpy_balances(has_heat_of_reaction=True)


def test_add_total_enthalpy_balances_dh_rxn_rate_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)
    m.fs.cv.add_phase_component_balances(has_rate_reactions=True)

    eb = m.fs.cv.add_total_enthalpy_balances(has_heat_of_reaction=True)
    assert isinstance(m.fs.cv.heat_of_reaction, Expression)


def test_add_total_enthalpy_balances_dh_rxn_equil_rxns():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=True)
    m.fs.cv.add_phase_component_balances(has_equilibrium_reactions=True)

    eb = m.fs.cv.add_total_enthalpy_balances(has_heat_of_reaction=True)
    assert isinstance(m.fs.cv.heat_of_reaction, Expression)


# -----------------------------------------------------------------------------
# Test unsupported energy balance types
def test_add_phase_enthalpy_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_phase_enthalpy_balances()


def test_add_phase_energy_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_phase_energy_balances()


def test_add_total_energy_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_total_energy_balances()


# -----------------------------------------------------------------------------
# Test add total pressure balances
def test_add_total_pressure_balances_default():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_pressure_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 1
    assert isinstance(m.fs.cv.pressure, Var)
    assert isinstance(m.fs.cv.pressure_linking_constraint, Constraint)
    assert isinstance(m.fs.cv.pressure_dx, DerivativeVar)

    with pytest.raises(KeyError):
        assert m.fs.cv.pressure_balance[0, 0]
    assert type(m.fs.cv.pressure_balance[0, 1]) is \
        _GeneralConstraintData


def test_add_total_pressure_balances_default_FFD():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "FORWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_pressure_balances()

    assert isinstance(mb, Constraint)
    assert len(mb) == 1
    assert isinstance(m.fs.cv.pressure, Var)
    assert isinstance(m.fs.cv.pressure_linking_constraint, Constraint)
    assert isinstance(m.fs.cv.pressure_dx, DerivativeVar)

    with pytest.raises(KeyError):
        assert m.fs.cv.pressure_balance[0, 1]
    assert type(m.fs.cv.pressure_balance[0, 0]) is \
        _GeneralConstraintData


def test_add_total_pressure_balances_deltaP():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    mb = m.fs.cv.add_total_pressure_balances(has_pressure_change=True)

    assert isinstance(mb, Constraint)
    assert len(mb) == 1
    assert isinstance(m.fs.cv.deltaP, Var)


def test_add_total_pressure_balances_custom_term():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=False)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.test_var = Var(m.fs.cv.flowsheet().config.time)

    def custom_method(t, x):
        return m.fs.cv.test_var[t]

    mb = m.fs.cv.add_total_pressure_balances(custom_term=custom_method)

    assert isinstance(mb, Constraint)
    assert len(mb) == 1


# -----------------------------------------------------------------------------
# Test unsupported momentum balance types
def test_add_phase_pressure_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_phase_pressure_balances()


def test_add_phase_momentum_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_phase_momentum_balances()


def test_add_total_momentum_balances():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    with pytest.raises(BalanceTypeNotSupportedError):
        m.fs.cv.add_total_momentum_balances()


# -----------------------------------------------------------------------------
# Test model checks, initialize and release_state
def test_model_checks():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    m.fs.cv.model_check()

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            assert m.fs.cv.properties[t, x].check is True
            assert m.fs.cv.reactions[t, x].check is True


def test_initialize():
    m = ConcreteModel()
    m.fs = Flowsheet(default={"dynamic": False})
    m.fs.pp = PhysicalParameterTestBlock()
    m.fs.rp = ReactionParameterTestBlock(default={"property_package": m.fs.pp})
    m.fs.pp.del_component(m.fs.pp.phase_equilibrium_idx)

    m.fs.cv = ControlVolume1DBlock(default={
                "property_package": m.fs.pp,
                "reaction_package": m.fs.rp,
                "transformation_method": "dae.finite_difference",
                "transformation_scheme": "BACKWARD",
                "finite_elements": 10})

    m.fs.cv.add_geometry()
    m.fs.cv.add_state_blocks(has_phase_equilibrium=True)
    m.fs.cv.add_reaction_blocks(has_equilibrium=False)

    f = m.fs.cv.initialize(state_args={})

    for t in m.fs.time:
        for x in m.fs.cv.length_domain:
            assert m.fs.cv.properties[t, x].init_test is True
            assert m.fs.cv.reactions[t, x].init_test is True
