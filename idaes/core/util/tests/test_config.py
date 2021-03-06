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
Tests for config utility methods.

Author: Andrew Lee
"""
import pytest
from pyomo.environ import ConcreteModel, Set
from pyomo.dae import ContinuousSet
from pyomo.network import Port
from idaes.core import (declare_process_block_class,
                        PhysicalParameterBlock,
                        StateBlock,
                        StateBlockData,
                        ReactionParameterBlock,
                        useDefault)
from idaes.core.util.config import (is_physical_parameter_block,
                                    is_reaction_parameter_block,
                                    is_state_block,
                                    list_of_floats,
                                    list_of_strings,
                                    is_port,
                                    is_time_domain,
                                    is_transformation_method,
                                    is_transformation_scheme)
from idaes.core.util.exceptions import ConfigurationError


@declare_process_block_class("ParameterBlock")
class _ParameterBlock(PhysicalParameterBlock):
    def build(self):
        pass


def test_is_physical_parameter_block_passes():
    # Make an instance of a Parameter Block
    p = ParameterBlock()

    # Check that is_physical_parameter_block returns the ParameterBlock
    assert p == is_physical_parameter_block(p)


def test_is_physical_parameter_block_useDefault():
    assert useDefault == is_physical_parameter_block(useDefault)


def test_is_physical_parameter_block_fails():
    # Test that is_physical_parameter_block returns ConfigurationError with
    # wrong input
    m = ConcreteModel()

    with pytest.raises(ConfigurationError):
        is_physical_parameter_block(m)  # Non Parameter Block Pyomo object
    with pytest.raises(ConfigurationError):
        is_physical_parameter_block("foo")  # str
    with pytest.raises(ConfigurationError):
        is_physical_parameter_block(1)  # int


@declare_process_block_class("RParameterBlock")
class _RParameterBlock(ReactionParameterBlock):
    def build(self):
        pass


def test_is_reaction_parameter_block_passes():
    # Make an instance of a Parameter Block
    r = RParameterBlock()

    # Check that is_reaction_parameter_block returns the ReactionParameterBlock
    assert r == is_reaction_parameter_block(r)


def test_is_reaction_parameter_block_useDefault():
    # No useDefault option for is_reaction_parameter_block
    with pytest.raises(ConfigurationError):
        is_reaction_parameter_block(useDefault)


def test_is_reaction_parameter_block_fails():
    # Test that is_reaction_parameter_block returns ConfigurationError with
    # wrong input
    m = ConcreteModel()

    with pytest.raises(ConfigurationError):
        is_reaction_parameter_block(m)  # Non Parameter Block Pyomo object
    with pytest.raises(ConfigurationError):
        is_reaction_parameter_block("foo")  # str
    with pytest.raises(ConfigurationError):
        is_reaction_parameter_block(1)  # int


@declare_process_block_class("TestStateBlock", block_class=StateBlock)
class StateTestBlockData(StateBlockData):
    def build(self):
        pass


def test_is_state_block_passes():
    # Make an instance of a TestStateBlock
    s = TestStateBlock()

    # Check that is_state_block returns the TestStateBlock
    assert s == is_state_block(s)


def test_is_state_block_fails():
    # Test that is_state_block returns ConfigurationError with wrong input
    m = ConcreteModel()

    with pytest.raises(ConfigurationError):
        is_state_block(m)  # Non Parameter Block Pyomo object
    with pytest.raises(ConfigurationError):
        is_state_block("foo")  # str
    with pytest.raises(ConfigurationError):
        is_state_block(1)  # int


def test_list_of_strings():
    # Test list_of_strings=returns correctly
    assert list_of_strings(1) == ['1']  # int
    assert list_of_strings([1, 2, 3]) == ['1', '2', '3']  # list of ints
    assert list_of_strings(1.0) == ['1.0']  # float
    # list of floats
    assert list_of_strings([1.0, 2.0, 3.0]) == ['1.0', '2.0', '3.0']
    assert list_of_strings("foo") == ["foo"]  # str
    assert list_of_strings(["foo", "bar"]) == ["foo", "bar"]  # list of strs


def test_list_of_strings_errors():
    # Test that list_of_strings fails correctly
    with pytest.raises(ConfigurationError):
        list_of_strings({"foo": "bar"})  # dict


def test_list_of_floats():
    # Test list_of_floats returns correctly
    assert list_of_floats(1) == [1.0]  # int
    assert list_of_floats([1, 2, 3]) == [1.0, 2.0, 3.0]  # list of ints
    assert list_of_floats(1.0) == [1.0]  # float
    assert list_of_floats([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]  # list of floats


def test_list_of_floats_errors():
    # Test that list_of_floats fails correctly
    with pytest.raises(ValueError):
        list_of_floats("foo")  # str
    with pytest.raises(ValueError):
        list_of_floats(["foo", "bar"])  # list of strs
    with pytest.raises(ValueError):
        list_of_floats({"foo": "bar"})  # dict


def test_is_port():
    # Test that is_port passes a valid port
    m = ConcreteModel()
    m.c = Port()
    assert isinstance(is_port(m.c), Port)


def test_is_port_errors():
    # Test that is_port returns errors when not given a Port
    with pytest.raises(ConfigurationError):
        is_port("foo")  # str
    with pytest.raises(ConfigurationError):
        is_port(["foo", "bar"])  # list of strs
    with pytest.raises(ConfigurationError):
        is_port({"foo": "bar"})  # dict
    with pytest.raises(ConfigurationError):
        is_port(1.0)  # float
    with pytest.raises(ConfigurationError):
        is_port(1)  # int


def test_is_time_domain():
    # Test that is_time_domain accepts Sets and ContinuousSets
    m = ConcreteModel()

    m.s = Set(initialize=[1, 2, 3, 4])
    m.cs = ContinuousSet(bounds=[0, 1])

    assert isinstance(is_time_domain(m.s), Set)
    assert isinstance(is_time_domain(m.cs), ContinuousSet)


def test_is_time_domain_errors():
    # Test that is_time_domain returns errors when not Set or ContinuousSet

    with pytest.raises(ConfigurationError):
        assert is_time_domain("foo")
    with pytest.raises(ConfigurationError):
        assert is_time_domain(["foo", "bar"])
    with pytest.raises(ConfigurationError):
        assert is_time_domain(("foo", "bar"))
    with pytest.raises(ConfigurationError):
        assert is_time_domain({"foo": "bar"})
    with pytest.raises(ConfigurationError):
        assert is_time_domain(1)
    with pytest.raises(ConfigurationError):
        assert is_time_domain(1.0)


def test_is_transformation_method():
    assert is_transformation_method("dae.finite_difference") == \
        "dae.finite_difference"

    assert is_transformation_method("dae.collocation") == \
        "dae.collocation"

    with pytest.raises(ConfigurationError):
        is_transformation_method("dea.finite_difference")


def test_is_transformation_scheme():
    assert is_transformation_scheme("BACKWARD") == "BACKWARD"
    assert is_transformation_scheme("FORWARD") == "FORWARD"
    assert is_transformation_scheme("LAGRANGE-RADAU") == "LAGRANGE-RADAU"
    assert is_transformation_scheme("LAGRANGE-LEGENDRE") == "LAGRANGE-LEGENDRE"

    with pytest.raises(ConfigurationError):
        is_transformation_scheme("foo")
