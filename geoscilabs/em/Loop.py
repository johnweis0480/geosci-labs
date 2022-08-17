import copy
import numpy as np

from scipy.interpolate import interp2d, LinearNDInterpolator
from scipy.special import ellipk, ellipe
from scipy.sparse import spdiags, csr_matrix, eye, kron, hstack, vstack, diags
from scipy.constants import mu_0
from scipy.sparse.linalg import spsolve, splu

import matplotlib.pyplot as plt
import matplotlib.patches as patches

from pymatsolver import Pardiso


def rectangular_plane_layout(mesh, corner, closed=False, I=1.0):
    """
    corner: sorted list of four corners (x,y,z)

    2--3
    |  |
    1--4

    y
    |
    |--> x

    Output:
    Js

    """

    Jx = np.zeros(mesh.nEx)
    Jy = np.zeros(mesh.nEy)
    Jz = np.zeros(mesh.nEz)

    indy1 = np.logical_and(
        np.logical_and(
            np.logical_and(
                mesh.gridEy[:, 0] >= corner[0, 0], mesh.gridEy[:, 0] <= corner[1, 0]
            ),
            np.logical_and(
                mesh.gridEy[:, 1] >= corner[0, 1], mesh.gridEy[:, 1] <= corner[1, 1]
            ),
        ),
        (mesh.gridEy[:, 2] == corner[0, 2]),
    )
    indx1 = np.logical_and(
        np.logical_and(
            np.logical_and(
                mesh.gridEx[:, 0] >= corner[1, 0], mesh.gridEx[:, 0] <= corner[2, 0]
            ),
            np.logical_and(
                mesh.gridEx[:, 1] >= corner[1, 1], mesh.gridEx[:, 1] <= corner[2, 1]
            ),
        ),
        (mesh.gridEx[:, 2] == corner[1, 2]),
    )
    indy2 = np.logical_and(
        np.logical_and(
            np.logical_and(
                mesh.gridEy[:, 0] >= corner[2, 0], mesh.gridEy[:, 0] <= corner[3, 0]
            ),
            np.logical_and(
                mesh.gridEy[:, 1] <= corner[2, 1], mesh.gridEy[:, 1] >= corner[3, 1]
            ),
        ),
        (mesh.gridEy[:, 2] == corner[2, 2]),
    )

    if closed:
        indx2 = np.logical_and(
            np.logical_and(
                np.logical_and(
                    mesh.gridEx[:, 0] >= corner[0, 0], mesh.gridEx[:, 0] <= corner[3, 0]
                ),
                np.logical_and(
                    mesh.gridEx[:, 1] >= corner[0, 1], mesh.gridEx[:, 1] <= corner[3, 1]
                ),
            ),
            (mesh.gridEx[:, 2] == corner[0, 2]),
        )

    else:
        indx2 = []

    Jy[indy1] = -I
    Jx[indx1] = -I
    Jy[indy2] = I
    Jx[indx2] = I

    J = np.hstack((Jx, Jy, Jz))
    J = J * mesh.edge

    return J


def BiotSavart(locs, mesh, Js):
    """
    Compute the magnetic field generated by current discretized on a mesh using Biot-Savart law

    Input:
    locs: observation locations
    mesh: mesh on which the current J is discretized
    Js: discretized source current in A-m (Finite Volume formulation)

    Output:
    B: magnetic field [Bx,By,Bz]
    """

    c = mu_0 / (4 * np.pi)
    nwire = np.sum(Js != 0.0)
    ind = np.where(Js != 0.0)
    ind = ind[0]
    B = np.zeros([locs.shape[0], 3])
    gridE = np.vstack([mesh.gridEx, mesh.gridEy, mesh.gridEz])

    for i in range(nwire):
        # x wire
        if ind[i] < mesh.nEx:
            r = locs - gridE[ind[i]]
            I = Js[ind[i]] * np.hstack(
                [
                    np.ones([locs.shape[0], 1]),
                    np.zeros([locs.shape[0], 1]),
                    np.zeros([locs.shape[0], 1]),
                ]
            )
            cr = np.cross(I, r)
            rsq = np.linalg.norm(r, axis=1) ** 3.0
            B = B + c * cr / rsq[:, None]
        # y wire
        elif ind[i] < mesh.nEx + mesh.nEy:
            r = locs - gridE[ind[i]]
            I = Js[ind[i]] * np.hstack(
                [
                    np.zeros([locs.shape[0], 1]),
                    np.ones([locs.shape[0], 1]),
                    np.zeros([locs.shape[0], 1]),
                ]
            )
            cr = np.cross(I, r)
            rsq = np.linalg.norm(r, axis=1) ** 3.0
            B = B + c * cr / rsq[:, None]
        # z wire
        elif ind[i] < mesh.nEx + mesh.nEy + mesh.nEz:
            r = locs - gridE[ind[i]]
            I = Js[ind[i]] * np.hstack(
                [
                    np.zeros([locs.shape[0], 1]),
                    np.zeros([locs.shape[0], 1]),
                    np.ones([locs.shape[0], 1]),
                ]
            )
            cr = np.cross(I, r)
            rsq = np.linalg.norm(r, axis=1) ** 3.0
            B = B + c * cr / rsq[:, None]
        else:
            print("error: index of J out of bounds (number of edges in the mesh)")

    return B


def analytic_infinite_wire(obsloc, wireloc, orientation, I=1.0):
    """
    Compute the response of an infinite wire with orientation 'orientation'
    and current I at the obsvervation locations obsloc

    Output:
    B: magnetic field [Bx,By,Bz]
    """

    n, d = obsloc.shape
    t, d = wireloc.shape
    d = np.sqrt(
        np.dot(obsloc ** 2.0, np.ones([d, t]))
        + np.dot(np.ones([n, d]), (wireloc.T) ** 2.0)
        - 2.0 * np.dot(obsloc, wireloc.T)
    )
    distr = np.amin(d, axis=1, keepdims=True)
    idxmind = d.argmin(axis=1)
    r = obsloc - wireloc[idxmind]

    # orient = np.c_[[orientation for i in range(obsloc.shape[0])]]
    B = (mu_0 * I) / (2 * np.pi * (distr ** 2.0)) * np.cross(orientation, r)

    return B


def mag_dipole(m, obsloc):
    """
    Compute the response of an infinitesimal mag dipole at location (0,0,0)
    with orientation X and magnetic moment 'm'
    at the obsvervation locations obsloc

    Output:
    B: magnetic field [Bx,By,Bz]
    """

    loc = np.r_[[[0.0, 0.0, 0.0]]]
    n, d = obsloc.shape
    t, d = loc.shape
    d = np.sqrt(
        np.dot(obsloc ** 2.0, np.ones([d, t]))
        + np.dot(np.ones([n, d]), (loc.T) ** 2.0)
        - 2.0 * np.dot(obsloc, loc.T)
    )
    d = d.flatten()
    ind = np.where(d == 0.0)
    d[ind] = 1e6
    x = obsloc[:, 0]
    y = obsloc[:, 1]
    z = obsloc[:, 2]
    # orient = np.c_[[orientation for i in range(obsloc.shape[0])]]
    Bz = (mu_0 * m) / (4 * np.pi * (d ** 3.0)) * (3.0 * ((z ** 2.0) / (d ** 2.0)) - 1.0)
    By = (mu_0 * m) / (4 * np.pi * (d ** 3.0)) * (3.0 * (z * y) / (d ** 2.0))
    Bx = (mu_0 * m) / (4 * np.pi * (d ** 3.0)) * (3.0 * (x * z) / (d ** 2.0))

    B = np.vstack([Bx, By, Bz]).T

    return B


def circularloop(a, obsloc, I=1.0):
    """
    From Simpson, Lane, Immer, Youngquist 2001
    Compute the magnetic field B response of a current loop
    of radius 'a' with intensity 'I'.

    input:
    a: radius in m
    obsloc: obsvervation locations

    Output:
    B: magnetic field [Bx,By,Bz]
    """
    x = np.atleast_2d(obsloc[:, 0]).T
    y = np.atleast_2d(obsloc[:, 1]).T
    z = np.atleast_2d(obsloc[:, 2]).T

    # r = np.linalg.norm(obsloc, axis=1)
    # loc = np.r_[[[0.0, 0.0, 0.0]]]
    n, d = obsloc.shape
    r2 = x ** 2.0 + y ** 2.0 + z ** 2.0
    rho2 = x ** 2.0 + y ** 2.0
    alpha2 = a ** 2.0 + r2 - 2 * a * np.sqrt(rho2)
    beta2 = a ** 2.0 + r2 + 2 * a * np.sqrt(rho2)
    k2 = 1 - (alpha2 / beta2)
    # lbda = x ** 2.0 - y ** 2.0
    C = mu_0 * I / np.pi

    Bx = ((C * x * z) / (2 * alpha2 * np.sqrt(beta2) * rho2)) * (
        (a ** 2.0 + r2) * ellipe(k2) - alpha2 * ellipk(k2)
    )
    Bx[np.isnan(Bx)] = 0.0

    By = ((C * y * z) / (2 * alpha2 * np.sqrt(beta2) * rho2)) * (
        (a ** 2.0 + r2) * ellipe(k2) - alpha2 * ellipk(k2)
    )
    By[np.isnan(By)] = 0.0

    Bz = (C / (2.0 * alpha2 * np.sqrt(beta2))) * (
        (a ** 2.0 - r2) * ellipe(k2) + alpha2 * ellipk(k2)
    )
    Bz[np.isnan(Bz)] = 0.0

    # print(Bx.shape)
    # print(By.shape)
    # print(Bz.shape)
    B = np.hstack([Bx, By, Bz])

    return B
