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
Heat Exchanger Models.
"""

__author__ = "John Eslick"

import logging
from enum import Enum

# Import Pyomo libraries
from pyomo.environ import (Var, log, Expression, Constraint,
                           PositiveReals, SolverFactory, ExternalFunction)
from pyomo.common.config import ConfigBlock, ConfigValue, In
from pyomo.opt import TerminationCondition

# Import IDAES cores
from idaes.core import (ControlVolume0DBlock,
                        declare_process_block_class,
                        EnergyBalanceType,
                        MomentumBalanceType,
                        MaterialBalanceType,
                        UnitModelBlockData,
                        useDefault)
from idaes.core.util.config import is_physical_parameter_block
from idaes.core.util.exceptions import ConfigurationError
from idaes.core.util.misc import add_object_reference
from idaes.functions import functions_lib

_log = logging.getLogger(__name__)


class HeatExchangerFlowPattern(Enum):
    countercurrent = 1
    cocurrent = 2
    crossflow = 3


def delta_temperature_lmtd_rule(b, t):
    """
    This is a rule for a temperaure difference expression to calculate
    :math:`\Delta T` in the heat exchanger model using log-mean temperature
    difference (LMTD).  It can be supplied to "delta_temperature_rule"
    HeatExchanger configuration option.
    """
    dT1 = b.delta_temperature_in[t]
    dT2 = b.delta_temperature_out[t]
    return (dT1 - dT2) / (log(dT1) - log(dT2))


def delta_temperature_amtd_rule(b, t):
    """
    This is a rule for a temperaure difference expression to calculate
    :math:`\Delta T` in the heat exchanger model using arithmetic-mean
    temperature difference (AMTD).  It can be supplied to
    "delta_temperature_rule" HeatExchanger configuration option.
    """
    dT1 = b.delta_temperature_in[t]
    dT2 = b.delta_temperature_out[t]
    return (dT1 + dT2) * 0.5


def delta_temperature_underwood_rule(b, t):
    """
    This is a rule for a temperaure difference expression to calculate
    :math:`\Delta T` in the heat exchanger model using log-mean temperature
    difference (LMTD) approximation given by Underwood (1970).  It can be
    supplied to "delta_temperature_rule" HeatExchanger configuration option.
    """
    dT1 = b.delta_temperature_in[t]
    dT2 = b.delta_temperature_out[t]
    return ((dT1**(1.0/3.0) + dT2**(1.0/3.0))/2.0)**3


def delta_temperature_underwood2_rule(b, t):
    """
    This is a rule for a temperaure difference expression to calculate
    :math:`\Delta T` in the heat exchanger model using log-mean temperature
    difference (LMTD) approximation given by Underwood (1970).  It can be
    supplied to "delta_temperature_rule" HeatExchanger configuration option.
    This uses a cube root function that works with negative numbers returning
    the real negative root.  This function should always evaluate successfully.
    """
    dT1 = b.delta_temperature_in[t]
    dT2 = b.delta_temperature_out[t]
    return ((b.cbrt(dT1) + b.cbrt(dT2))/2.0)**3


def _heat_transfer_rule(b, t):
    """
    This is the default rule used by the HeatExchanger model to calculate heat
    transfer (:math:`Q = UA\Delta T`).
    """
    u = b.overall_heat_transfer_coefficient[t]
    a = b.area
    q = b.heat_duty[t]
    deltaT = b.delta_temperature[t]
    return 0 == (u*a*deltaT - q)*b.side_1.scaling_factor_energy


def _cross_flow_heat_transfer_rule(b, t):
    """
    This is the default rule used by the HeatExchanger model to calculate heat
    transfer (:math:`Q = UA\Delta T`).
    """
    u = b.overall_heat_transfer_coefficient[t]
    a = b.area
    q = b.heat_duty[t]
    deltaT = b.delta_temperature[t]
    f = b.crossflow_factor[t]
    return 0 == (f*u*a*deltaT - q)*b.side_1.scaling_factor_energy


def _make_heater_control_volume(o, name, config,
                                dynamic=None, has_holdup=None):
    """
    This is seperated from the main heater class so it can be reused to create
    control volumes for different types of heat exchange models.
    """
    if dynamic is None:
        dynamic = config.dynamic
    if has_holdup is None:
        has_holdup = config.has_holdup
    # we have to attach this control volume to the model for the rest of
    # the steps to work
    o.add_component(name, ControlVolume0DBlock(default={
        "dynamic": dynamic,
        "has_holdup": has_holdup,
        "property_package": config.property_package,
        "property_package_args": config.property_package_args}))
    control_volume = getattr(o, name)
    # Add inlet and outlet state blocks to control volume
    control_volume.add_state_blocks(
        has_phase_equilibrium=config.has_phase_equilibrium)
    # Add material balance
    control_volume.add_material_balances(
        balance_type=config.material_balance_type,
        has_phase_equilibrium=config.has_phase_equilibrium)
    # add energy balance
    control_volume.add_energy_balances(
        balance_type=config.energy_balance_type,
        has_heat_transfer=True)
    # add momentum balance
    control_volume.add_momentum_balances(
        balance_type=config.momentum_balance_type,
        has_pressure_change=config.has_pressure_change)
    return control_volume


def _make_heater_config_block(config):
    """
    Declare configuration options for HeaterData block.
    """
    config.declare("material_balance_type", ConfigValue(
        default=MaterialBalanceType.componentPhase,
        domain=In(MaterialBalanceType),
        description="Material balance construction flag",
        doc="""Indicates what type of mass balance should be constructed,
**default** - MaterialBalanceType.componentPhase.
**Valid values:** {
**MaterialBalanceType.none** - exclude material balances,
**MaterialBalanceType.componentPhase** - use phase component balances,
**MaterialBalanceType.componentTotal** - use total component balances,
**MaterialBalanceType.elementTotal** - use total element balances,
**MaterialBalanceType.total** - use total material balance.}"""))
    config.declare("energy_balance_type", ConfigValue(
        default=EnergyBalanceType.enthalpyTotal,
        domain=In(EnergyBalanceType),
        description="Energy balance construction flag",
        doc="""Indicates what type of energy balance should be constructed,
**default** - EnergyBalanceType.enthalpyTotal.
**Valid values:** {
**EnergyBalanceType.none** - exclude energy balances,
**EnergyBalanceType.enthalpyTotal** - single ethalpy balance for material,
**EnergyBalanceType.enthalpyPhase** - ethalpy balances for each phase,
**EnergyBalanceType.energyTotal** - single energy balance for material,
**EnergyBalanceType.energyPhase** - energy balances for each phase.}"""))
    config.declare("momentum_balance_type", ConfigValue(
        default=MomentumBalanceType.pressureTotal,
        domain=In(MomentumBalanceType),
        description="Momentum balance construction flag",
        doc="""Indicates what type of momentum balance should be constructed,
**default** - MomentumBalanceType.pressureTotal.
**Valid values:** {
**MomentumBalanceType.none** - exclude momentum balances,
**MomentumBalanceType.pressureTotal** - single pressure balance for material,
**MomentumBalanceType.pressurePhase** - pressure balances for each phase,
**MomentumBalanceType.momentumTotal** - single momentum balance for material,
**MomentumBalanceType.momentumPhase** - momentum balances for each phase.}"""))
    config.declare("has_phase_equilibrium", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Phase equilibrium construction flag",
        doc="""Indicates whether terms for phase equilibrium should be
constructed, **default** = False.
**Valid values:** {
**True** - include phase equilibrium terms
**False** - exclude phase equilibrium terms.}"""))
    config.declare("has_pressure_change", ConfigValue(
        default=False,
        domain=In([True, False]),
        description="Pressure change term construction flag",
        doc="""Indicates whether terms for pressure change should be
constructed,
**default** - False.
**Valid values:** {
**True** - include pressure change terms,
**False** - exclude pressure change terms.}"""))
    config.declare("property_package", ConfigValue(
        default=useDefault,
        domain=is_physical_parameter_block,
        description="Property package to use for control volume",
        doc="""Property parameter object used to define property calculations,
**default** - useDefault.
**Valid values:** {
**useDefault** - use default package from parent model or flowsheet,
**PropertyParameterObject** - a PropertyParameterBlock object.}"""))
    config.declare("property_package_args", ConfigBlock(
        implicit=True,
        description="Arguments to use for constructing property packages",
        doc="""A ConfigBlock with arguments to be passed to a property block(s)
and used when constructing these,
**default** - None.
**Valid values:** {
see property package for documentation.}"""))


def _make_heat_exchanger_config(config):
    """
    Declare configuration options for HeatExchangerData block.
    """
    config.declare("side_1", ConfigBlock(
        implicit=True,
        description="Config block for side_1",
        doc="""A config block used to construct the side_1 control volume."""))
    config.declare("side_2", ConfigBlock(
        implicit=True,
        description="Config block for side_2",
        doc="""A config block used to construct the side_2 control volume."""))
    _make_heater_config_block(config.side_1)
    _make_heater_config_block(config.side_2)
    config.declare("delta_temperature_rule", ConfigValue(
        default=delta_temperature_lmtd_rule,
        description="Rule for equation for temperature difference"))
    config.declare("flow_pattern", ConfigValue(
        default=HeatExchangerFlowPattern.countercurrent,
        domain=In(HeatExchangerFlowPattern),
        description="Heat exchanger flow pattern",
        doc="""Heat exchanger flow pattern,
**default** - HeatExchangerFlowPattern.countercurrent.
**Valid values:** {
**HeatExchangerFlowPattern.countercurrent** - countercurrent flow,
**HeatExchangerFlowPattern.cocurrent** - cocurrent flow,
**HeatExchangerFlowPattern.crossflow** - cross flow, factor times
countercurrent temperature difference.}"""))


@declare_process_block_class("Heater", doc="Simple 0D heater/cooler model.")
class HeaterData(UnitModelBlockData):
    """
    Simple 0D heater unit.
    Unit model to add or remove heat from a material.
    """
    CONFIG = UnitModelBlockData.CONFIG()
    _make_heater_config_block(CONFIG)

    def build(self):
        """
        Building model
        Args:
            None
        Returns:
            None
        """
        # Call UnitModel.build to setup dynamics
        super(HeaterData, self).build()
        # Add Control Volume
        _make_heater_control_volume(self, "control_volume", self.config)
        # Add Ports
        self.add_inlet_port()
        self.add_outlet_port()
        # Add a convienient reference to heat duty.
        add_object_reference(self, "heat_duty", self.control_volume.heat)


@declare_process_block_class("HeatExchanger",
                             doc="Simple 0D heat exchanger model.")
class HeatExchangerData(UnitModelBlockData):
    """
    Simple 0D heat exchange unit.
    Unit model to transfer heat from one material to another.
    """
    CONFIG = UnitModelBlockData.CONFIG()
    _make_heat_exchanger_config(CONFIG)

    def set_scaling_factor_energy(self, f):
        """
        This function sets scaling_factor_energy for both side_1 and side_2.
        This factor multiplies the energy balance and heat transfer equations
        in the heat exchnager.  The value of this factor should be about
        1/(expected heat duty).

        Args:
            f: Energy balance scaling factor
        """
        self.side_1.scaling_factor_energy.value = f
        self.side_2.scaling_factor_energy.value = f

    def build(self):
        """
        Building model

        Args:
            None
        Returns:
            None
        """
        # Call UnitModel.build to setup dynamics
        super().build()
        config = self.config
        # Add variables
        self.overall_heat_transfer_coefficient = Var(
                self.flowsheet().config.time,
                domain=PositiveReals,
                initialize=100,
                doc="Overall heat transfer coefficient")
        self.overall_heat_transfer_coefficient.latex_symbol = "U"
        self.area = Var(domain=PositiveReals,
                        initialize=1000,
                        doc="Heat exchange area")
        self.area.latex_symbol = "A"
        if config.flow_pattern == HeatExchangerFlowPattern.crossflow:
            self.crossflow_factor = Var(
                    self.flowsheet().config.time,
                    initialize=1,
                    doc="Factor to adjust coutercurrent flow heat transfer "
                        "calculation for cross flow.")

        if config.delta_temperature_rule == delta_temperature_underwood2_rule:
            # Define a cube root function that return the real negative root
            # for the cube root of a negative number.
            self.cbrt = ExternalFunction(library=functions_lib(),
                                         function="cbrt")

        # Add Control Volumes
        _make_heater_control_volume(self, "side_1", config.side_1,
                                    dynamic=config.dynamic,
                                    has_holdup=config.has_holdup)
        _make_heater_control_volume(self, "side_2", config.side_2,
                                    dynamic=config.dynamic,
                                    has_holdup=config.has_holdup)
        # Add Ports
        self.add_inlet_port(name="inlet_1", block=self.side_1)
        self.add_inlet_port(name="inlet_2", block=self.side_2)
        self.add_outlet_port(name="outlet_1", block=self.side_1)
        self.add_outlet_port(name="outlet_2", block=self.side_2)
        # Add convienient references to heat duty.
        add_object_reference(self, "heat_duty", self.side_2.heat)
        self.side_1.heat.latex_symbol = "Q_1"
        self.side_2.heat.latex_symbol = "Q_2"

        @self.Expression(self.flowsheet().config.time,
                         doc="Temperature difference at the side 1 inlet end")
        def delta_temperature_in(b, t):
            if b.config.flow_pattern == \
                    HeatExchangerFlowPattern.countercurrent:
                return b.side_1.properties_in[t].temperature -\
                       b.side_2.properties_out[t].temperature
            elif b.config.flow_pattern == HeatExchangerFlowPattern.cocurrent:
                return b.side_1.properties_in[t].temperature -\
                       b.side_2.properties_in[t].temperature
            elif b.config.flow_pattern == HeatExchangerFlowPattern.crossflow:
                return b.side_1.properties_in[t].temperature -\
                       b.side_2.properties_out[t].temperature
            else:
                raise ConfigurationError(
                        "Flow pattern {} not supported"
                        .format(b.config.flow_pattern))
        @self.Expression(self.flowsheet().config.time,
                         doc="Temperature difference at the side 1 outlet end")
        def delta_temperature_out(b, t):
            if b.config.flow_pattern == \
                    HeatExchangerFlowPattern.countercurrent:
                return b.side_1.properties_out[t].temperature -\
                       b.side_2.properties_in[t].temperature
            elif b.config.flow_pattern == HeatExchangerFlowPattern.cocurrent:
                return b.side_1.properties_out[t].temperature -\
                       b.side_2.properties_out[t].temperature
            elif b.config.flow_pattern == HeatExchangerFlowPattern.crossflow:
                return b.side_1.properties_out[t].temperature -\
                       b.side_2.properties_in[t].temperature

        # Add a unit level energy balance
        def unit_heat_balance_rule(b, t):
            return 0 == self.side_1.heat[t] + self.side_2.heat[t]
        self.unit_heat_balance = Constraint(
            self.flowsheet().config.time, rule=unit_heat_balance_rule)
        # Add heat transfer equation
        self.delta_temperature = Expression(
            self.flowsheet().config.time,
            rule=config.delta_temperature_rule,
            doc="Temperature difference driving force for heat transfer")
        self.delta_temperature.latex_symbol = "\\Delta T"

        if config.flow_pattern == HeatExchangerFlowPattern.crossflow:
            self.heat_transfer_equation = Constraint(
                self.flowsheet().config.time, rule=_cross_flow_heat_transfer_rule)
        else:
            self.heat_transfer_equation = Constraint(
                self.flowsheet().config.time, rule=_heat_transfer_rule)

    def initialize(self, state_args_1=None, state_args_2=None, outlvl=0,
                   solver='ipopt', optarg={'tol': 1e-6}, duty=1000):
        """
        Heat exchanger initialization method.

        Args:
            state_args_1 : a dict of arguments to be passed to the property
                initialization for side_1 (see documentation of the specific
                property package) (default = {}).
            state_args_2 : a dict of arguments to be passed to the property
                initialization for side_2 (see documentation of the specific
                property package) (default = {}).
            outlvl : sets output level of initialisation routine
                     * 0 = no output (default)
                     * 1 = return solver state for each step in routine
                     * 2 = return solver state for each step in subroutines
                     * 3 = include solver output infomation (tee=True)
            optarg : solver options dictionary object (default={'tol': 1e-6})
            solver : str indicating which solver to use during
                     initialization (default = 'ipopt')
            duty : an initial guess for the amount of heat transfered
                (default = 10000)

        Returns:
            None

        """
        # Set solver options
        tee = True if outlvl >= 3 else False
        opt = SolverFactory(solver)
        opt.options = optarg
        flags1 = self.side_1.initialize(outlvl=outlvl - 1,
                                        optarg=optarg,
                                        solver=solver,
                                        state_args=state_args_1)

        if outlvl > 0:
            _log.info('{} Initialization Step 1a (side_1) Complete.'
                      .format(self.name))

        flags2 = self.side_2.initialize(outlvl=outlvl - 1,
                                        optarg=optarg,
                                        solver=solver,
                                        state_args=state_args_2)

        if outlvl > 0:
            _log.info('{} Initialization Step 1b (side_2) Complete.'
                      .format(self.name))
        # ---------------------------------------------------------------------
        # Solve unit without heat transfer equation
        self.heat_transfer_equation.deactivate()
        self.side_2.heat.fix(duty)
        results = opt.solve(self, tee=tee, symbolic_solver_labels=True)
        if outlvl > 0:
            if results.solver.termination_condition == \
                    TerminationCondition.optimal:
                _log.info('{} Initialization Step 2 Complete.'
                          .format(self.name))
            else:
                _log.warning('{} Initialization Step 2 Failed.'
                             .format(self.name))
        self.side_2.heat.unfix()
        self.heat_transfer_equation.activate()
        # ---------------------------------------------------------------------
        # Solve unit
        results = opt.solve(self, tee=tee, symbolic_solver_labels=True)
        if outlvl > 0:
            if results.solver.termination_condition == \
                    TerminationCondition.optimal:
                _log.info('{} Initialization Step 3 Complete.'
                          .format(self.name))
            else:
                _log.warning('{} Initialization Step 3 Failed.'
                             .format(self.name))
        # ---------------------------------------------------------------------
        # Release Inlet state
        self.side_1.release_state(flags1, outlvl - 1)
        self.side_2.release_state(flags2, outlvl - 1)

        if outlvl > 0:
            _log.info('{} Initialization Complete.'.format(self.name))
