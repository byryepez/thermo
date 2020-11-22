# -*- coding: utf-8 -*-
'''Chemical Engineering Design Library (ChEDL). Utilities for process modeling.
Copyright (C) 2019, 2020 Caleb Bell <Caleb.Andrew.Bell@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This module contains functions for identifying phases as liquid, solid, and
gas.

Solid identification is easy using the solid phase identification parameter.
There is never more than one gas by definition. For pure species, the
phase identification parameter is a clear vapor-liquid differentiator.
However for mixtures, there is no clear calcuation that can be performed to
identify the phase of a mixture. Many different criteria that have been
proposed are included here.

For reporting bugs, adding feature requests, or submitting pull requests,
please use the `GitHub issue tracker <https://github.com/CalebBell/thermo/>`_.

.. contents:: :local:

Phase Identification Criteria
=============================

Main Interfaces
---------------
.. autofunction:: identify_sort_phases
.. autofunction:: sort_phases
.. autofunction:: identity_phase_states

Scoring Functions
-----------------
.. autofunction:: score_phases_VL
.. autofunction:: score_phases_S
.. autofunction:: vapor_score_traces
.. autofunction:: vapor_score_Tpc
.. autofunction:: vapor_score_Vpc
.. autofunction:: vapor_score_Tpc_weighted
.. autofunction:: vapor_score_Tpc_Vpc
.. autofunction:: vapor_score_Wilson
.. autofunction:: vapor_score_Poling
.. autofunction:: vapor_score_PIP
.. autofunction:: vapor_score_Bennett_Schmidt

'''

from __future__ import division
__all__ = ['vapor_score_Tpc', 'vapor_score_Vpc',
           'vapor_score_Tpc_weighted', 'vapor_score_Tpc_Vpc',
           'vapor_score_Wilson', 'vapor_score_Poling',
           'vapor_score_PIP', 'vapor_score_Bennett_Schmidt',
           'vapor_score_traces',

           'score_phases_S', 'score_phases_VL', 'identity_phase_states',
           'S_ID_METHODS', 'VL_ID_METHODS',

           'sort_phases', 'identify_sort_phases',

           'WATER_FIRST', 'WATER_LAST', 'WATER_NOT_SPECIAL',
           'WATER_SORT_METHODS', 'KEY_COMPONENTS_SORT', 'PROP_SORT',
           'SOLID_SORT_METHODS', 'LIQUID_SORT_METHODS'
           ]


from chemicals.rachford_rice import Rachford_Rice_flash_error, flash_inner_loop
from chemicals.flash_basic import Wilson_K_value
from chemicals.utils import phase_identification_parameter, Vm_to_rho

def vapor_score_Tpc(T, Tcs, zs):
    # Does not work for pure compounds
    # Basic
    Tpc =  0.0
    for i in range(len(zs)):
        Tpc += zs[i]*Tcs[i]
    return T - Tpc

def vapor_score_Vpc(V, Vcs, zs):
    # Basic
    Vpc =  0.0
    for i in range(len(zs)):
        Vpc += zs[i]*Vcs[i]
    return V - Vpc

def vapor_score_Tpc_weighted(T, Tcs, Vcs, zs, r1=1.0):
    # ECLIPSE method, r1 for tuning
    weight_sum = 0.0
    for i in range(len(zs)):
        weight_sum += zs[i]*Vcs[i]

    Tpc =  0.0
    for i in range(len(zs)):
        Tpc += zs[i]*Tcs[i]*Vcs[i]
    Tpc *= r1/weight_sum

    return T - Tpc

def vapor_score_Tpc_Vpc(T, V, Tcs, Vcs, zs):
    # Basic. Different mixing rules could be used to tune the system.
    Tpc =  0.0
    for i in range(len(zs)):
        Tpc += zs[i]*Tcs[i]
    Vpc =  0.0
    for i in range(len(zs)):
        Vpc += zs[i]*Vcs[i]
    return V*T*T - Vpc*Tpc*Tpc


def vapor_score_Wilson(T, P, zs, Tcs, Pcs, omegas):
    N = len(zs)
    if N == 1:
        Psat = Wilson_K_value(T, P, Tcs[0], Pcs[0], omegas[0])*P
        # Lower than vapor pressure - gas; higher than the vapor pressure - liquid
        return P - Psat
    # Does not work for pure compounds
    # Posivie - vapor, negative - liquid
    Ks = [Wilson_K_value(T, P, Tcs[i], Pcs[i], omegas[i]) for i in range(N)]
    # Consider a vapor fraction of more than 0.5 a vapor
    return flash_inner_loop(zs, Ks)[0] - 0.5
    # Go back to the error once unit tested
#    return Rachford_Rice_flash_error(V_over_F=0.5, zs=zs, Ks=Ks)


def vapor_score_Poling(kappa):
    r'''Compute a vapor score representing how vapor-like a phase is
    (higher, above zero = more vapor like) using the isothermal compressibility
    `kappa` concept by Poling [1]_.

    .. math::
        \text{score} = (\kappa - 0.005 \text{atm}^{-1})

    Parameters
    ----------
    kappa : float
        Isothermal coefficient of compressibility, [1/Pa]

    Returns
    -------
    score : float
        Vapor like score, [-]

    Examples
    --------
    CO2 vapor properties computed with Peng-Robinson at 300 K and 1 bar:

    >>> vapor_score_Poling(1.0054239121594122e-05)
    1.013745778995

    n-hexane liquid properties computed with Peng-Robinson at 300 K and 10 bar:

    >>> vapor_score_Poling(2.121777078782957e-09)
    -0.00478501093

    Notes
    -----
    A second criteria which is not implemented as it does not fit with the
    scoring concept is for liquids:

    .. math::
        \frac{0.9}{P} < \beta < \frac{3}{P}

    References
    ----------
    .. [1] Poling, Bruce E., Edward A. Grens, and John M. Prausnitz.
       "Thermodynamic Properties from a Cubic Equation of State: Avoiding
       Trivial Roots and Spurious Derivatives." Industrial & Engineering
       Chemistry Process Design and Development 20, no. 1 (January 1, 1981):
       127-30. https://doi.org/10.1021/i200012a019.
    '''
    # There is also a second criteria for the vapor phase
    return kappa*101325 - .005

def vapor_score_PIP(V, dP_dT, dP_dV, d2P_dV2, d2P_dVdT):
    r'''Compute a vapor score representing how vapor-like a phase is
    (higher, above zero = more vapor like) using the PIP concept.

    .. math::
        \text{score} = -(\Pi - 1)

    .. math::
        \Pi = V \left[\frac{\frac{\partial^2 P}{\partial V \partial T}}
        {\frac{\partial P }{\partial T}}- \frac{\frac{\partial^2 P}{\partial
        V^2}}{\frac{\partial P}{\partial V}} \right]

    Parameters
    ----------
    V : float
        Molar volume at `T` and `P`, [m^3/mol]
    dP_dT : float
        Derivative of `P` with respect to `T`, [Pa/K]
    dP_dV : float
        Derivative of `P` with respect to `V`, [Pa*mol/m^3]
    d2P_dV2 : float
        Second derivative of `P` with respect to `V`, [Pa*mol^2/m^6]
    d2P_dVdT : float
        Second derivative of `P` with respect to both `V` and `T`, [Pa*mol/m^3/K]

    Returns
    -------
    score : float
        Vapor like score, [-]

    Examples
    --------
    CO2 vapor properties computed with Peng-Robinson at 300 K and 1 bar:

    >>> vapor_score_PIP(0.024809176851423774, 337.0119286073647, -4009021.959558917, 321440573.3615088, -13659.63987996052)
    0.016373735005

    n-hexane liquid properties computed with Peng-Robinson at 300 K and 10 bar:

    >>> vapor_score_PIP(0.00013038156684574785, 578477.8796379718, -3614798144591.8984, 4.394997991022487e+17, -20247865009.795322)
    -10.288635225

    References
    ----------
    .. [1] Venkatarathnam, G., and L. R. Oellrich. "Identification of the Phase
       of a Fluid Using Partial Derivatives of Pressure, Volume, and
       Temperature without Reference to Saturation Properties: Applications in
       Phase Equilibria Calculations." Fluid Phase Equilibria 301, no. 2
       (February 25, 2011): 225-33. doi:10.1016/j.fluid.2010.12.001.
    '''
    return -(phase_identification_parameter(V, dP_dT, dP_dV, d2P_dV2, d2P_dVdT) - 1.0)

def vapor_score_Bennett_Schmidt(dbeta_dT):
    r'''Compute a vapor score representing how vapor-like a phase is
    (higher, above zero = more vapor like) using the Bennet-Schmidt
    temperature derivative of isobaric expansion suggestion.

    .. math::
        \text{score} = -\left(\frac{\partial \beta}{\partial T}\right)

    Parameters
    ----------
    dbeta_dT : float
        Temperature derivative of isobaric coefficient of a thermal
        expansion, [1/K^2]

    Returns
    -------
    score : float
        Vapor like score, [-]

    Examples
    --------
    CO2 vapor properties computed with Peng-Robinson at 300 K and 1 bar:

    >>> vapor_score_Bennett_Schmidt(-1.1776172267959163e-05)
    1.1776172267959163e-05

    n-hexane liquid properties computed with Peng-Robinson at 300 K and 10 bar:

    >>> vapor_score_PIP(7.558572848883679e-06)
    -7.558572848883679e-06

    References
    ----------
    .. [1] Bennett, Jim, and Kurt A. G. Schmidt. "Comparison of Phase
       Identification Methods Used in Oil Industry Flow Simulations." Energy &
       Fuels 31, no. 4 (April 20, 2017): 3370-79.
       https://doi.org/10.1021/acs.energyfuels.6b02316.
    '''
    return -dbeta_dT

def vapor_score_traces(zs, CASs, trace_CASs=['74-82-8', '7727-37-9'], Tcs=None):
    # traces should be the lightest species - high = more vapor like
    if trace_CASs is not None:
        for trace_CAS in trace_CASs:
            try:
                return zs[CASs.index(trace_CAS)]
            except ValueError:
                # trace component not in mixture
                pass

    # Return the composition of the compound with the lowest critical temp
    comp = 0.0
    Tc_min = 1e100
    for i in range(len(zs)):
        if Tcs[i] < Tc_min:
            comp = zs[i]
            Tc_min = Tcs[i]
    return comp


VL_ID_TPC = 'Tpc'
VL_ID_VPC = 'Vpc'
VL_ID_TPC_VC_WEIGHTED = 'Tpc Vpc weighted'
VL_ID_TPC_VPC = 'Tpc Vpc'
VL_ID_WILSON = 'Wilson'
VL_ID_POLING = 'Poling'
VL_ID_PIP = 'PIP'
VL_ID_BS = 'Bennett-Schmidt'
VL_ID_TRACES = 'Traces'

VL_ID_METHODS = [VL_ID_TPC, VL_ID_VPC, VL_ID_TPC_VC_WEIGHTED, VL_ID_TPC_VPC,
                 VL_ID_WILSON, VL_ID_POLING, VL_ID_PIP, VL_ID_BS, VL_ID_TRACES]

S_ID_D2P_DVDT = 'd2P_dVdT'
S_ID_METHODS = [S_ID_D2P_DVDT]

def score_phases_S(phases, constants, correlations, method, S_ID_settings=None):
    # The higher the score (above zero), the more solid-like
    if method == S_ID_D2P_DVDT:
        scores = [i.d2P_dVdT() for i in phases]
    return scores

def score_phases_VL(phases, constants, correlations, method):
    r'''Score all phases given the provided parameters and a selected method.

    A score above zero indicates a potential gas. More than one phase may have
    a score above zero, in which case the highest scoring phase is the gas,
    and the other is a liquid.

    Parameters
    ----------
    phases : list[:obj:`thermo.phases.Phase`]
        Phases to be identified and sorted, [-]
    constants : :obj:`thermo.chemical_package.ChemicalConstantsPackage`
        Constants used in the identification, [-]
    correlations : :obj:`thermo.chemical_package.PropertyCorrelationPackage`
        Correlations used in the identification, [-]
    method : str
        Setting configuring how the scoring is performed, [-]

    Returns
    -------
    scores : list[float]
        Scores for the phases in the order provided, [-]

    Notes
    -----

    Examples
    --------
    >>> from thermo import ChemicalConstantsPackage, PropertyCorrelationPackage, CEOSGas, CEOSLiquid, PRMIX, HeatCapacityGas
    >>> constants = ChemicalConstantsPackage(CASs=['124-38-9', '110-54-3'], MWs=[44.0095, 86.17536], names=['carbon dioxide', 'hexane'], omegas=[0.2252, 0.2975], Pcs=[7376460.0, 3025000.0], Tbs=[194.67, 341.87], Tcs=[304.2, 507.6], Tms=[216.65, 178.075])
    >>> correlations = PropertyCorrelationPackage(constants=constants, skip_missing=True, HeatCapacityGases=[HeatCapacityGas(best_fit=(50.0, 1000.0, [-3.1115474168865828e-21, 1.39156078498805e-17, -2.5430881416264243e-14, 2.4175307893014295e-11, -1.2437314771044867e-08, 3.1251954264658904e-06, -0.00021220221928610925, 0.000884685506352987, 29.266811602924644])), HeatCapacityGas(best_fit=(200.0, 1000.0, [1.3740654453881647e-21, -8.344496203280677e-18, 2.2354782954548568e-14, -3.4659555330048226e-11, 3.410703030634579e-08, -2.1693611029230923e-05, 0.008373280796376588, -1.356180511425385, 175.67091124888998]))])
    >>> T, P, zs = 300.0, 1e6, [.5, .5]
    >>> eos_kwargs = {'Pcs': constants.Pcs, 'Tcs': constants.Tcs, 'omegas': constants.omegas}
    >>> gas = CEOSGas(PRMIX, eos_kwargs, HeatCapacityGases=correlations.HeatCapacityGases, T=T, P=P, zs=zs)
    >>> liq = CEOSLiquid(PRMIX, eos_kwargs, HeatCapacityGases=correlations.HeatCapacityGases, T=T, P=P, zs=zs)

    Score of phase identification parameter :obj:`vapor_score_PIP`:

    >>> score_phases_VL([gas, liq], constants, correlations, method='PIP')
    [1.6409446310, -7.5692120928]
    '''
    # The higher the score (above zero), the more vapor-like
    if phases:
        T = phases[0].T
    if method == VL_ID_TPC:
        Tcs = constants.Tcs
        scores = [vapor_score_Tpc(T, Tcs, i.zs) for i in phases]
    elif method == VL_ID_VPC:
        Vcs = constants.Vcs
        scores = [vapor_score_Vpc(i.V(), Vcs, i.zs) for i in phases]
    elif method == VL_ID_TPC_VC_WEIGHTED:
        Tcs = constants.Tcs
        Vcs = constants.Vcs
        scores = [vapor_score_Tpc_weighted(T, Tcs, Vcs, i.zs) for i in phases]
    elif method == VL_ID_TPC_VPC:
        Tcs = constants.Tcs
        Vcs = constants.Vcs
        scores = [vapor_score_Tpc_Vpc(T, i.V(), Tcs, Vcs, i.zs) for i in phases]
    elif method == VL_ID_WILSON:
        Tcs = constants.Tcs
        Pcs = constants.Pcs
        omegas = constants.omegas
        scores = [vapor_score_Wilson(T, i.P, i.zs, Tcs, Pcs, omegas) for i in phases]
    elif method == VL_ID_POLING:
        scores = [vapor_score_Poling(i.kappa()) for i in phases]
    elif method == VL_ID_PIP:
        scores = [-(i.PIP() - 1.00000000000001) for i in phases]
#        scores = [vapor_score_PIP(i.V(), i.dP_dT(), i.dP_dV(),
#                                           i.d2P_dV2(), i.d2P_dVdT()) for i in phases]
    elif method == VL_ID_BS:
        scores = [vapor_score_Bennett_Schmidt(i.disobaric_expansion_dT()) for i in phases]
    elif method == VL_ID_TRACES:
        CASs = constants.CASs
        Tcs = constants.Tcs
        scores = [vapor_score_traces(i.zs, CASs, Tcs=Tcs) for i in phases]
    return scores


def identity_phase_states(phases, constants, correlations, VL_method=VL_ID_PIP,
                          S_method=S_ID_D2P_DVDT,
                          VL_ID_settings=None, S_ID_settings=None,
                          skip_solids=False):
    # TODO - unit test
    # TODO - optimize
    # Takes a while

    force_phases = [i.force_phase for i in phases]
    forced = True
    phases_to_ID = []
    phases_to_ID_idxs = []
    for i, s in enumerate(force_phases):
        if s is None:
            forced = False
            # TODO avoid scoring phases with force phase
            phases_to_ID.append(phases[i])
            phases_to_ID_idxs.append(i)

    if not forced:
        VL_scores = score_phases_VL(phases, constants, correlations,
                                    method=VL_method)
        if not skip_solids:
            S_scores = score_phases_S(phases, constants, correlations,
                                      method=S_method, S_ID_settings=S_ID_settings)

    solids = []
    liquids = []
    possible_gases = []
    possible_gas_scores = []

    for i in range(len(phases)):
        if force_phases[i] is not None:
            if force_phases[i] == 'l':
                liquids.append(phases[i])
            if force_phases[i] == 's':
                solids.append(phases[i])
            if force_phases[i] == 'g':
                possible_gases.append(phases[i])
        elif not skip_solids and S_scores[i] >= 0.0:
            solids.append(phases[i])
        elif VL_scores[i] >= 0.0:
            possible_gases.append(phases[i])
            possible_gas_scores.append(VL_scores[i])
        else:
            liquids.append(phases[i])

    # Handle multiple matches as gas
    possible_gas_count = len(possible_gases)
    if possible_gas_count > 1:
        gas = possible_gases[possible_gas_scores.index(max(possible_gas_scores))]
        for possible_gas in possible_gases:
            if possible_gas is not gas:
                liquids.append(possible_gas)
        possible_gases[:] = (gas,)
    elif possible_gas_count == 1:
        gas = possible_gases[0]
    else:
        gas = None

    return gas, liquids, solids



DENSITY_MASS = 'DENSITY_MASS'
DENSITY = 'DENSITY'
ISOTHERMAL_COMPRESSIBILITY = 'ISOTHERMAL_COMPRESSIBILITY'
HEAT_CAPACITY = 'HEAT_CAPACITY'
L_SORT_PROPS = S_SORT_PROPS = [DENSITY_MASS, DENSITY, ISOTHERMAL_COMPRESSIBILITY,
                HEAT_CAPACITY]

WATER_FIRST = 'water first'
WATER_LAST = 'water last'
WATER_NOT_SPECIAL = 'water not special'

WATER_SORT_METHODS = [WATER_FIRST, WATER_LAST, WATER_NOT_SPECIAL]

KEY_COMPONENTS_SORT = 'key components'
PROP_SORT = 'prop'
SOLID_SORT_METHODS = LIQUID_SORT_METHODS = [PROP_SORT, KEY_COMPONENTS_SORT]

def key_cmp_sort(phases, cmps, cmps_neg):
    # TODO
    return phases

def mini_sort_phases(phases, sort_method, prop, cmps, cmps_neg,
                     reverse=True, constants=None):
    if sort_method == PROP_SORT:
        if prop == DENSITY_MASS:
            keys = []
            MWs = constants.MWs
            for p in phases:
                zs = p.zs
                MW = 0.0
                for i in constants.cmps:
                    MW += zs[i]*MWs[i]
                keys.append(Vm_to_rho(p.V(), MW))

            # for i in phases:
            #     i.constants = constants
            # keys = [i.rho_mass() for i in phases]
        elif prop == DENSITY:
            keys = [i.rho() for i in phases]
        elif prop == ISOTHERMAL_COMPRESSIBILITY:
            keys = [i.isobaric_expansion() for i in phases]
        elif prop == HEAT_CAPACITY:
            keys = [i.Cp() for i in phases]
        phases = [p for _, p in sorted(zip(keys, phases))]
        if reverse:
            phases.reverse()
    elif sort_method == KEY_COMPONENTS_SORT:
        phases = key_cmp_sort(phases, cmps, cmps_neg)
    return phases

def sort_phases(liquids, solids, constants, settings):

    if len(liquids) > 1:
        liquids = mini_sort_phases(liquids, sort_method=settings.liquid_sort_method,
                         prop=settings.liquid_sort_prop,
                         cmps=settings.liquid_sort_cmps,
                         cmps_neg=settings.liquid_sort_cmps_neg,
                         reverse=settings.phase_sort_higher_first, constants=constants)

        # Handle water special
        if settings.water_sort != WATER_NOT_SPECIAL:
            # water phase - phase with highest fraction water
            water_index = constants.water_index
            if water_index is not None:
                water_zs = [i.zs[water_index] for i in liquids]
                water_max_zs = max(water_zs)
                if water_max_zs > 1e-4:
                    water_phase_index = water_zs.index(water_max_zs)
                    water = liquids.pop(water_phase_index)
                    if settings.water_sort == WATER_LAST:
                        liquids.append(water)
                    elif settings.water_sort == WATER_FIRST:
                        liquids.insert(water)
    if len(solids) > 1:
        solids = mini_sort_phases(solids, sort_method=settings.solid_sort_method,
                         prop=setings.solid_sort_prop,
                         cmps=settings.solid_sort_cmps,
                         cmps_neg=settings.solid_sort_cmps_neg,
                         reverse=settings.phase_sort_higher_first, constants=constants)
    return liquids, solids


def identify_sort_phases(phases, betas, constants, correlations, settings,
                         skip_solids=False):
    r'''Identify and sort all phases given the provided parameters.

    Parameters
    ----------
    phases : list[:obj:`thermo.phase.Phase`]
        Phases to be identified and sorted, [-]
    betas : list[float]
        Phase molar fractions, [-]
    constants : :obj:`thermo.chemical_package.ChemicalConstantsPackage`
        Constants used in the identification, [-]
    correlations : :obj:`thermo.chemical_package.PropertyCorrelationPackage`
        Correlations used in the identification, [-]
    settings : :obj:`thermo.bulk.BulkSettings`
        Settings object controlling the phase ID, [-]
    skip_solids : bool
        Set this to True if no phases are provided which can represent a solid phase, [-]

    Returns
    -------
    gas : :obj:`thermo.phase.Phase`
        Gas phase, if one was identified, [-]
    liquids : list[:obj:`thermo.phase.Phase`]
        Liquids that were identified and sorted, [-]
    solids : list[:obj:`thermo.phase.Phase`]
        solids that were identified and sorted, [-]
    betas : list[float]
        Sorted phase molar fractions, in order (gas, liquids..., solids...) [-]

    Notes
    -----

    Examples
    --------

    '''
    gas, liquids, solids = identity_phase_states(phases, constants, correlations,
                              VL_method=settings.VL_ID,
                              S_method=settings.S_ID,
                              VL_ID_settings=settings.VL_ID_settings,
                              S_ID_settings=settings.S_ID_settings,
                              skip_solids=skip_solids)
    if liquids or solids:
        liquids, solids = sort_phases(liquids, solids, constants, settings)
    if betas is not None:
        new_betas = []
        if gas is not None:
            new_betas.append(betas[phases.index(gas)])
        for liquid in liquids:
            new_betas.append(betas[phases.index(liquid)])
        for solid in solids:
            new_betas.append(betas[phases.index(solid)])
        betas = new_betas
    return gas, liquids, solids, betas


