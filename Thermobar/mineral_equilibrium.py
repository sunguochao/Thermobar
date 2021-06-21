import numpy as np
import matplotlib.pyplot as plt
from functools import partial
import inspect
import warnings as w
import numbers
import pandas as pd


from Thermobar.core import *

## Equilibrium things for Olivine
def calculate_eq_olivine(Kd, *, Liq_Mgno):
    '''calculates equilibrium forsterite contents based on inputtted liquid Mg# and Kd Fe-Mg
     '''
    return 1 / ((Kd / Liq_Mgno) + (1 - Kd))

def calculate_ol_fo(ol_comps):
    Fo=(ol_comps['MgO_Ol']/40.3044)/((ol_comps['MgO_Ol']/40.3044)+(ol_comps['FeOt_Ol']/71.844))
    return Fo

def calculate_liq_mgno(liq_comps, Fe3FeT_Liq=None):
    liq_comps_c=liq_comps.copy()
    if Fe3FeT_Liq is not None:
        liq_comps_c['Fe3FeT_Liq']=Fe3FeT_Liq
    Mgno=(liq_comps['MgO_Ol']/40.3044)/((liq_comps['MgO_Ol']/40.3044)+(liq_comps_c['Fe3FeT_Liq']*liq_comps['FeOt_Ol']/71.844))
    return Fo

def calculate_toplis2005_kd(X_fo, *, SiO2_mol, Na2O_mol, K2O_mol, P, H2O, T):
    '''
    calculates olivine-liq Kd Fe-Mg using the expression of Toplis, 2005.
    '''
    SiO2_mol = 100 * SiO2_mol
    Na2O_mol = 100 * Na2O_mol
    K2O_mol = 100 * K2O_mol
    P = P * 1000
    R = 8.3144626181
    PSI_SiO2_60plus = (11 - 5.5 * (100 / (100 - SiO2_mol))) * \
        np.exp(-0.13 * (K2O_mol + Na2O_mol))
    PSI_SiO2_60minus = (0.46 * (100 / (100 - SiO2_mol)) - 0.93) * \
        (K2O_mol + Na2O_mol) + (-5.33 * (100 / (100 - SiO2_mol)) + 9.69)
    Adjusted_Si_Ksparalis_60plus = SiO2_mol + \
        PSI_SiO2_60plus * (Na2O_mol + K2O_mol)
    Adjusted_Si_Ksparalis_60minus = SiO2_mol + \
        PSI_SiO2_60minus * (Na2O_mol + K2O_mol)
    Adjusted_Si_Ksparalis_H2O_60plus = Adjusted_Si_Ksparalis_60plus + 0.8 * H2O
    Adjusted_Si_Ksparalis_H2O_60minus = Adjusted_Si_Ksparalis_60minus + 0.8 * H2O

    Kd_Toplis_60plus = np.exp((-6766 / (R * T) - 7.34 / R) + np.log(0.036 * Adjusted_Si_Ksparalis_H2O_60plus - 0.22)
                              + (3000 * (1 - 2 * X_fo)) / (R * T) + (0.035 * (P - 1)) / (R * T))
    Kd_Toplis_60minus = np.exp((-6766 / (R * T) - 7.34 / R) + np.log(0.036 * Adjusted_Si_Ksparalis_H2O_60minus - 0.22)
                               + (3000 * (1 - 2 * X_fo)) / (R * T) + (0.035 * (P - 1)) / (R * T))
    if isinstance(SiO2_mol, int) or isinstance(SiO2_mol, float):
        if SiO2_mol > 60:
            Kd_Toplis = Kd_Toplis_60plus
        if SiO2_mol < 60:
            Kd_Toplis = Kd_Toplis_60minus
    else:
        Kd_Toplis = np.empty(len(SiO2_mol), dtype=float)

        for i in range(0, len(SiO2_mol)):
            if SiO2_mol[i] > 60:
                Kd_Toplis[i] = Kd_Toplis_60plus[i]
            if SiO2_mol[i] < 60:
                Kd_Toplis[i] = Kd_Toplis_60minus[i]
    return Kd_Toplis


def calculate_eq_ol_content(liq_comps, Kd_model, ol_comps=None, T=None, P=None,
Fe3FeT_Liq=None, ol_fo=None, H2O_Liq=None):
    '''calculates equilibrium forsterite contents based on inputtted liquid compositions.


   Parameters
    -------

    liq_comps: DataFrame
        Liquid compositions with column headings SiO2_Ol, MgO_Ol etc.


    Kd_model: str
        Specify which Kd model you wish to use.
        "Roeder1970": uses Kd=0.3+0.03 (Not sensitive to P, T, or Ol Fo content)

        "Matzen2011": uses Kd=0.34+0.012 (Not sensitive to P, T, or Ol Fo content)

        "Toplis2005": calculates Kd based on melt SiO2, Na2O, K2O, P, T, H2O, Ol Fo content.
        Users can specify a ol_fo content, or the function iterates Kd and Fo and returns both.

        "All": Returns outputs for all models

    Fe3FeT: optional, float or int.
        overwrites Fe3FeT_Liq in liq_comps DataFrame

    Additional required inputs for Toplis, 2005:
        P: Pressure in kbar
        T: Temperature in Kelvin
        H2O: melt H2O content
        Optional:
            ol_fo: If specify Fo content (decimal, 0-1), calculates Kd
            Else, will iterate to find equilibrium Ol content and Kd.

    Returns
    -------
    pandas DataFrame
        returns equilibrium olivine contents (+- sigma for Roeder and Matzen).
        For Toplis, returns Kd-Ol Fo pair if an olivine-forsterite content wasn't specified

    '''
    if ol_comps is not None:
        ol_comps['Fo_meas']=calculate_ol_fo(ol_comps)
    if Fe3FeT_Liq is not None:
        liq_comps['Fe3FeT_Liq'] = Fe3FeT_Liq
    if H2O_Liq is not None:
        liq_comps['H2O_Liq'] = H2O_Liq

    liq = calculate_anhydrous_cat_fractions_liquid(liq_comps)
    Mgno = liq['Mg_Number_Liq_Fe3']
    if Kd_model == "Roeder1970" or Kd_model == "All":
        Eq_ol_03 = 1 / ((0.3 / Mgno) + (1 - 0.3))
        Eq_ol_027 = 1 / ((0.27 / Mgno) + (1 - 0.27))
        Eq_ol_033 = 1 / ((0.33 / Mgno) + (1 - 0.33))
        Kd_out_ro = pd.DataFrame(data={'Eq Fo (Roeder, Kd=0.3)': Eq_ol_03,
                                 'Eq Fo (Roeder, Kd=0.33)': Eq_ol_033, 'Eq Fo (Roeder, Kd=0.27)': Eq_ol_027})

    if Kd_model == "Matzen2011" or Kd_model == "All":
        Eq_ol_034 = 1 / ((0.34 / Mgno) + (1 - 0.34))
        Eq_ol_032 = 1 / ((0.328 / Mgno) + (1 - 0.328))
        Eq_ol_035 = 1 / ((0.352 / Mgno) + (1 - 0.352))
        Kd_out_mat = pd.DataFrame(data={'Eq Fo (Matzen, Kd=0.34)': Eq_ol_034,
                                  'Eq Fo (Matzen, Kd=0.352)': Eq_ol_035, 'Eq Fo (Matzen, Kd=0.328)': Eq_ol_032})


    if Kd_model == "Toplis2005" or Kd_model == "All":
        if P is None:
            raise Exception(
                'The Toplis Kd model is P-dependent, please enter P in kbar into the function')
        if T is None:
            raise Exception(
                'The Toplis Kd model is T-dependent, please enter T in Kelvin into the function')

        mol_perc = calculate_anhydrous_mol_fractions_liquid(liq_comps)
        SiO2_mol = mol_perc['SiO2_Liq_mol_frac']
        Na2O_mol = mol_perc['Na2O_Liq_mol_frac']
        K2O_mol = mol_perc['K2O_Liq_mol_frac']
        H2O_Liq = liq_comps['H2O_Liq']
        Kd_func = partial(calculate_toplis2005_kd, SiO2_mol=SiO2_mol,
                          Na2O_mol=Na2O_mol, K2O_mol=K2O_mol, P=P, H2O=H2O_Liq, T=T)
        if ol_fo is not None or ol_comps is not None:
            if ol_fo is not None and ol_comps is None:
                Kd_calc = Kd_func(ol_fo)
                Ol_calc = 1 / ((Kd_calc / Mgno) + (1 - Kd_calc))
            if ol_comps is not None:
                Kd_calc = Kd_func(ol_comps['Fo_meas'])
                Ol_calc = 1 / ((Kd_calc / Mgno) + (1 - Kd_calc))

            Kd_out_top = pd.DataFrame(
                    data={'Kd (Toplis, input Fo)': Kd_calc, 'Eq Fo (Toplis, input Fo)': Ol_calc})

        else:
            Eq_ol_func = partial(calculate_eq_olivine, Liq_Mgno=Mgno)
            iterations = 20
            Eq_ol_guess = 0.95
            for _ in range(iterations):
                Kd_Guess = Kd_func(Eq_ol_guess)
                Eq_ol_guess = Eq_ol_func(Kd_Guess)
                Kd_out_top = pd.DataFrame(
                    data={'Kd (Toplis, Iter)': Kd_Guess, 'Eq Fo (Toplis, Iter)': Eq_ol_guess})

    if Kd_model == "All":
        Kd_out = pd.concat([Kd_out_ro, Kd_out_mat, Kd_out_top], axis=1)
    if Kd_model == "Roeder1970":
        Kd_out=Kd_out_ro
    if Kd_model == "Matzen2011":
        Kd_out=Kd_out_mat
    if Kd_model == "Toplis2005":
        Kd_out=Kd_out_top

    if ol_comps is not None:
        Kd_out['Fo_meas']=ol_comps['Fo_meas']

    return Kd_out


def calculate_ol_rhodes_diagram_lines(
        Min_Mgno, Max_Mgno, KdMin=None, KdMax=None):
    '''
    Input minimum and maximum liquid Mg#, calculates lines for equilibrium Fo content using Roeder and Emslie (1970) and Matzen (2011) Kd values.

   Parameters
    -------

       Min_Mgno: float or int
            Min liquid Mg# you want equilibrium lines for

        Max_Mgno: float or int
            Max liquid Mg# you want equilibrium lines for

        KdMin: float
            Optional. Also returns line for a user-specified Minimum Kd.
        KdMax: float
             Optional. Also returns line for a user-specified Maximum Kd.

    Returns
        Mg#_Liq (100 points between Min)
        Eq_OlRoeder (Kd=0.3): Line calculated for Kd=0.3 (Roeder and Emslie, 1970 preferred value)
        Eq_OlRoeder (Kd=0.33): Line calculated for Kd=0.33 (Roeder and Emslie, 1970 +1 sigma)
        Eq_OlRoeder (Kd=0.27): Line calculated for Kd=0.27 (Roeder and Emslie, 1970 -1 sigma)
        Eq_OlMatzen (Kd=0.34): Line calculated for Kd=0.34 (Matzen et al. 2011 preferred value)
        Eq_OlMatzen (Kd=0.328): Line calculated for Kd=0.328 (Matzen et al. 2011 - 1 sigma)
        Eq_OlMatzen (Kd=0.352): Line calculated for Kd=0.352 (Matzen et al. 2011 + 1 sigma)
    If user specifies KdMin and KdMax also returns:
        Eq_Ol_KdMax=KdMax, Eq_Ol_KdMin=KdMin

    '''
    Mgno = np.linspace(Min_Mgno, Max_Mgno, 100)

    Mgno = np.linspace(Min_Mgno, Max_Mgno, 100)
    Eq_Roeder_03 = 1 / ((0.3 / Mgno) + (1 - 0.3))
    Eq_Roeder_027 = 1 / ((0.27 / Mgno) + (1 - 0.27))
    Eq_Roeder_033 = 1 / ((0.33 / Mgno) + (1 - 0.33))

    Eq_ol_034 = 1 / ((0.34 / Mgno) + (1 - 0.34))
    Eq_ol_032 = 1 / ((0.328 / Mgno) + (1 - 0.328))
    Eq_ol_035 = 1 / ((0.352 / Mgno) + (1 - 0.352))
    Kd_out_mat = pd.DataFrame(data={'Mg#_Liq': Mgno, 'Eq_Ol_Fo_Roeder (Kd=0.3)': Eq_Roeder_03,
                                    'Eq_Ol_Fo_Roeder (Kd=0.27)': Eq_Roeder_027,
                                    'Eq_Ol_Fo_Roeder (Kd=0.33)': Eq_Roeder_033,
                                    'Eq_Ol_Fo_Matzen (Kd=0.34)': Eq_ol_034,
                                    'Eq_Ol_Fo_Matzen (Kd=0.328)': Eq_ol_032,
                                    'Eq_Ol_Fo_Matzen (Kd=0.352)': Eq_ol_035})

    if KdMin is not None and KdMax is not None:
        Eq_ol_KdMin = 1 / ((KdMin / Mgno) + (1 - KdMin))
        Eq_ol_KdMax = 1 / ((KdMax / Mgno) + (1 - KdMax))
        Kd_out_mat2 = pd.DataFrame(data={'Eq_Ol_Fo (KdMin=' + str(
            KdMin) + ')': Eq_ol_KdMin, 'Eq_Ol_Fo (KdMax=' + str(KdMax) + ')': Eq_ol_KdMax})
        Kd_out_mat = pd.concat([Kd_out_mat, Kd_out_mat2], axis=1)

    return Kd_out_mat

## Equilibrium things for Pyroxene

def calculate_opx_rhodes_diagram_lines(
        Min_Mgno, Max_Mgno, T=None, KdMin=None, KdMax=None, liq_comps=None):
    '''
    Input minimum and maximum liquid Mg#, calculates lines for equilibrium
    Opx Mg# content using a variety of choices for Kd Fe-Mg.

   Parameters
    -------
    Min_Mgno: float or int.
        Min liquid Mg# you want equilibrium lines for

    Max_Mgno: float or int.
        Max liquid Mg# you want equilibrium lines for


    By default, returns Mg#s for 0.29+-0.06 (Putirka). Can get other outputs as
    well using:

        KdMin: float. Optional.
            Also returns line for a user-specified Minimum Kd.

        KdMax: float. Optional.
            Also returns line for a user-specified Maximum Kd.

        liq_comps: DataFrame. Optional
            Uses average cation fraction of XSi in the liquid to
            calculate Kd Fe-Mg using the expression = 0.4805 - 0.3733 XSi (Putirka, 2008)

   Returns
    -------
        Mg#_Liq (100 points between Min) and equilibrium Opx compositions depending on inputs.
        Returns headings corresponding to options selected above.

    '''
    Mgno = np.linspace(Min_Mgno, Max_Mgno, 100)

    Mgno = np.linspace(Min_Mgno, Max_Mgno, 100)
    Eq_023 = 1 / ((0.23 / Mgno) + (1 - 0.23))
    Eq_029 = 1 / ((0.29 / Mgno) + (1 - 0.29))
    Eq_035 = 1 / ((0.35 / Mgno) + (1 - 0.35))
    Kd_out_mat_s = pd.DataFrame(data={'Eq_Opx_Mg# (Kd=0.23)': Eq_023,
                                    'Eq_Opx_Mg# (Kd=0.29)': Eq_029,
                                    'Eq_Opx_Mg# (Kd=0.35)': Eq_035})
    Kd_out_mat = Kd_out_mat_s

    if KdMin is not None and KdMax is not None:
        Eq_ol_KdMin = 1 / ((KdMin / Mgno) + (1 - KdMin))
        Eq_ol_KdMax = 1 / ((KdMax / Mgno) + (1 - KdMax))
        Kd_out_mat_MM = pd.DataFrame(data={'Eq_Opx_Mg# (KdMin=' + str(
            KdMin) + ')': Eq_ol_KdMin, 'Eq_Opx_Mg# (KdMax=' + str(KdMax) + ')': Eq_ol_KdMax})
        Kd_out_mat = pd.concat([Kd_out_mat, Kd_out_mat_MM], axis=1)

    if liq_comps is not None:
        cat_frac = calculate_anhydrous_cat_fractions_liquid(liq_comps)
        Si_mean_frac = np.nanmean(cat_frac['SiO2_Liq_cat_frac'])
        Kd = 0.4805 - 0.3733 * Si_mean_frac
        Eq_Opx = 1 / ((Kd / Mgno) + (1 - Kd))
        Kd_p_1_s = Kd + 0.06
        Kd_m_1_s = Kd - 0.06
        Eq_Opx_p1sigma = 1 / ((Kd_p_1_s / Mgno) + (1 - Kd_p_1_s))
        Eq_Opx_m1sigma = 1 / ((Kd_m_1_s / Mgno) + (1 - Kd_m_1_s))
        Kd_out_mat_s = pd.DataFrame(data={'Kd_XSi_P2008': Kd, 'Eq_Opx_Mg# (Kd_XSi_P2008)':
        Eq_Opx, 'Eq_Opx_Mg# (Kd_XSi_P2008)+0.06': Eq_Opx_p1sigma,
        'Eq_Opx_Mg# (Kd_XSi_P2008)-0.06': Eq_Opx_m1sigma})

        Kd_out_mat = pd.concat([Kd_out_mat, Kd_out_mat_s], axis=1)



    Kd_out_mat.insert(0, "Mg#_Liq", Mgno)
    return Kd_out_mat


def calculate_cpx_rhodes_diagram_lines(
        Min_Mgno, Max_Mgno, T=None, KdMin=None, KdMax=None):
    '''
    Input minimum and maximum liquid Mg#, calculates lines for equilibrium Cpx Mg# contents based on user-specified Kd Fe-Mg options.

   Parameters
    -------


        Min_Mgno: float or int.
            Min liquid Mg# you want equilibrium lines for
        Max_Mgno: float or int.
            Max liquid Mg# you want equilibrium lines for

        By default, returns lines calculated using 0.28+-0.08 (Putirka, 2008).
        Can get other outputs as well using:

        T: float or int (optional)
            Temperature in Kelvin. returns lines calculated using Kd from T-sensitive eq 35 of Putirka (2008) (as well as +-0.08 error bounds)
        KdMin: float (optional)
            calculates equilibrium line for a user-specified Minimum Kd.
        KdMax: float (optional)
            calculates equilibrium line for a user-specified Minimum Kd
    Returns:
    -------
        Mg#_Liq (100 points between Min_Mgno and Max_Mgno), and a variety of equilibrium Cpx Mg#s


    '''

    Mgno = np.linspace(Min_Mgno, Max_Mgno, 100)
    Eq_02 = 1 / ((0.2 / Mgno) + (1 - 0.2))
    Eq_028 = 1 / ((0.28 / Mgno) + (1 - 0.28))
    Eq_036 = 1 / ((0.36 / Mgno) + (1 - 0.36))
    Kd_out_mat = pd.DataFrame(data={'Eq_Cpx_Mg# (Kd=0.28)': Eq_028,
                                        'Eq_Cpx_Mg# (Kd=0.2)': Eq_02, 'Eq_Cpx_Mg# (Kd=0.36)': Eq_036})


    if isinstance(T, int) or isinstance(T, float):
        Kd = np.exp(-0.107 - 1719 / T)
        Eq_Cpx = 1 / ((Kd / Mgno) + (1 - Kd))
        Kd_p_1_s = Kd + 0.08
        Kd_m_1_s = Kd - 0.08
        Eq_Cpx_p1sigma = 1 / ((Kd_p_1_s / Mgno) + (1 - Kd_p_1_s))
        Eq_Cpx_m1sigma = 1 / ((Kd_m_1_s / Mgno) + (1 - Kd_m_1_s))
        Kd_out_mat_s = pd.DataFrame(data={'Kd_Eq35_P2008': Kd, 'Eq_Cpx_Mg# (Kd from Eq 35 P2008)':
        Eq_Cpx, 'Eq_Cpx_Mg# (Eq 35 P2008)+0.08': Eq_Cpx_p1sigma,
        'Eq_Cpx_Mg# (Eq 35 P2008)-0.08': Eq_Cpx_m1sigma})
        Kd_out_mat=pd.concat([Kd_out_mat, Kd_out_mat_s], axis=1)


    if KdMin is not None and KdMax is not None:
        Eq_cpx_KdMin = 1 / ((KdMin / Mgno) + (1 - KdMin))
        Eq_cpx_KdMax = 1 / ((KdMax / Mgno) + (1 - KdMax))
        Kd_out_mat_MM = pd.DataFrame(data={'Eq_Cpx_Mg# (KdMin=' + str(
            KdMin) + ')': Eq_cpx_KdMin, 'Eq_Cpx_Mg# (KdMax=' + str(KdMax) + ')': Eq_cpx_KdMax})
        Kd_out_mat = pd.concat([Kd_out_mat, Kd_out_mat_MM], axis=1)

    Kd_out_mat.insert(0, "Mg#_Liq", Mgno)
    return Kd_out_mat



