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
Tests for math util methods.
"""

import pytest
from pyomo.environ import Block, ConcreteModel,  Constraint, \
                            Set, SolverFactory, Var, value
from pyomo.network import Port
from idaes.core.util.initialization import solve_indexed_blocks

__author__ = "Andrew Lee"


# See if ipopt is available and set up solver
if SolverFactory('ipopt').available():
    solver = SolverFactory('ipopt')
    solver.options = {'tol': 1e-6,
                      'mu_init': 1e-8,
                      'bound_push': 1e-8}
else:
    solver = None


@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_solve_indexed_block_list():
    # Create an indexed block and try to solve it
    m = ConcreteModel()
    m.s = Set(initialize=[1, 2, 3])

    def block_rule(b, x):
        b.v = Var(initialize=1.0)
        b.c = Constraint(expr=b.v == 2.0)
    m.b = Block(m.s, rule=block_rule)

    solve_indexed_blocks(solver=solver, blocks=[m.b])

    for i in m.s:
        assert value(m.b[i].v == 2.0)


@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_solve_indexed_block_IndexedBlock():
    # Create an indexed block and try to solve it
    m = ConcreteModel()
    m.s = Set(initialize=[1, 2, 3])

    def block_rule(b, x):
        b.v = Var(initialize=1.0)
        b.c = Constraint(expr=b.v == 2.0)
    m.b = Block(m.s, rule=block_rule)

    solve_indexed_blocks(solver=solver, blocks=m.b)

    for i in m.s:
        assert value(m.b[i].v == 2.0)


def test_solve_indexed_block_error():
    # Try solve_indexed_block on non-block object
    with pytest.raises(TypeError):
        solve_indexed_blocks(solver=None, blocks=[1, 2, 3])
