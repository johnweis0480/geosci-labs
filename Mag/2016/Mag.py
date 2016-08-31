#from fromFatiando import *
from fromSimPEG import Magnetics as MAG
from fromSimPEG import simpegCoordUtils as Utils

from scipy.constants import mu_0
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
from IPython.html.widgets import *
# import ipywidgets as widgets
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# monFile = "data2015/StudentData2015_Monday.csv"
# monData = pd.DataFrame(pd.read_csv(filename, header = 0))

# filename = "data2014/HZrebarProfile.csv"
# data = pd.DataFrame(pd.read_csv(filename, header = 0))
# loc = data["Distance"].values

diameter = 1.4e-2
length = 3.
xlim = np.r_[5., 25.]
rx_h = 1.9

Bincd = 70.205
Bdecd = 16.63
Bigrfd = 54399

# Depth of burial: Monday was 35cm. I believe that Wednesday was ~45cm


class definePrism(object):
    """
        Define a prism and its attributes

        Prism geometry:
            - dx, dy, dz: width, length and height of prism
            - depth : depth to top of prism
            - susc : susceptibility of prism
            - x0, y0 : center of prism in horizontal plane
            - pinc, pdec : inclination and declination of prism
    """

    x0, y0, z0, dx, dy, dz = 0., 0., 0., 1., 1., 1.
    pinc, pdec = 0., 0.


    # Define the nodes of the prism
    @property
    def xn(self):
        xn = np.asarray([-self.dx/2. + self.x0, self.dx/2. + self.x0])

        return xn

    @property
    def yn(self):
        yn = np.asarray([-self.dy/2. + self.y0, self.dy/2. + self.y0])

        return yn

    @property
    def zn(self):
        zn = np.asarray([-self.dz/2. + self.z0, self.dz/2. + self.z0])

        return zn

    @property
    def xc(self):
        xc = (self.xn[0] + self.xn[1]) / 2.

        return xc

    @property
    def yc(self):
        yc = (self.yn[0] + self.yn[1]) / 2.

        return yc

    @property
    def zc(self):
        zc = (self.zn[0] + self.zn[1]) / 2.

        return zc


class survey(object):

    rx_h = 1.9
    npts2D = 20
    xylim = 5.
    rxLoc = None

    @property
    def rxLoc(self):
        if getattr(self, '_rxLoc', None) is None:
            # Create survey locations
            X, Y = np.meshgrid(self.xr, self.yr)
            Z = np.ones(np.shape(X))*self.rx_h

            self._rxLoc = np.c_[Utils.mkvc(X), Utils.mkvc(Y), Utils.mkvc(Z)]

        return self._rxLoc

    @property
    def xr(self):
        nx = self.npts2D
        self._xr = np.linspace(-self.xylim, self.xylim, nx)

        return self._xr

    @property
    def yr(self):
        ny = self.npts2D
        self._yr = np.linspace(-self.xylim, self.xylim, ny)

        return self._yr


class problem(object):
    """
            Earth's field:
            - Binc, Bdec : inclination and declination of Earth's mag field
            - Bigrf : amplitude of earth's field in units of nT

        Remnance:
            - Q : Koenigsberger ratio
            - Rinc, Rdec : inclination and declination of remnance in block

    """
    Bdec, Binc, Bigrf = 90., 0., 50000.
    Q, rinc, rdec = 0., 0., 0.
    uType, mType = 'tf', 'induced'
    susc = 1.
    prism = None
    survey = None

    @property
    def Mind(self):
        # Define magnetization direction as sum of induced and remanence
        Mind = self.susc*self.Higrf*Utils.dipazm_2_xyz(self.Binc - self.prism.pinc,
                                                       self.Bdec - self.prism.pdec)

        return Mind

    @property
    def Mrem(self):
        Mrem = self.Q*self.susc*self.Higrf * \
               Utils.dipazm_2_xyz(self.rinc - self.prism.pinc, self.rdec - self.prism.pdec)

        return Mrem

    @property
    def Higrf(self):
        Higrf = self.Bigrf * 1e-9 / mu_0

        return Higrf

    @property
    def G(self):

        if getattr(self, '_G', None) is None:
            print "Computing G"

            rot = Utils.mkvc(Utils.dipazm_2_xyz(self.prism.pinc, self.prism.pdec))

            rxLoc = Utils.rotatePointsFromNormals(self.survey.rxLoc, rot, np.r_[0., 1., 0.],
                                                 np.r_[0, 0, 0])

            # Create the linear forward system
            self._G = MAG.Intrgl_Fwr_Op(self.prism.xn, self.prism.yn, self.prism.zn, rxLoc)

        return self._G

    def fields(self):

        if (self.mType == 'induced') or (self.mType == 'total'):

            b = self.G.dot(self.Mind)
            self.fieldi = self.extractFields(b)

        if (self.mType == 'remanent') or (self.mType == 'total'):

            b = self.G.dot(self.Mrem)

            self.fieldr = self.extractFields(b)

        if self.mType == 'induced':
            return self.fieldi
        elif self.mType == 'remanent':
            return self.fieldr
        elif self.mType == 'total':
            return self.fieldi, self.fieldr

    def extractFields(self, bvec):

        nD = bvec.shape[0]/3
        bvec = np.reshape(bvec, (3, nD))

        rot = Utils.mkvc(Utils.dipazm_2_xyz(-self.prism.pinc, -self.prism.pdec))

        bvec = Utils.rotatePointsFromNormals(bvec.T, rot, np.r_[0., 1., 0.],
                                             np.r_[0, 0, 0]).T

        if self.uType == 'bx':
            u = Utils.mkvc(bvec[0, :])

        if self.uType == 'by':
            u = Utils.mkvc(bvec[1, :])

        if self.uType == 'bz':
            u = Utils.mkvc(bvec[2, :])

        if self.uType == 'tf':
            # Projection matrix
            Ptmi = Utils.dipazm_2_xyz(self.Binc, self.Bdec).T

            u = Utils.mkvc(Ptmi.dot(bvec))

        return u

def profiledataRem(data, B0, x0, depth, susc, Q, rinc, rdec):
    if data is 'MonSt':
        filename = "data2015/StudentData2015_Monday.csv"
    elif data is 'WedSt':
        filename = "data2015/StudentData2015_Wednesday.csv"
    elif data is 'WedTA':
        filename = "data2015/TAData2015_Wednesday.csv"

    dat = pd.DataFrame(pd.read_csv(filename, header = 0))
    tf  = dat["Corrected Total Field Data (nT)"].values
    std = dat["Standard Deviation (nT)"].values
    loc = dat["Location (m)"].values
    teams = dat["Team"].values

    tfa = tf - B0

    # p = definePrism(length, diameter, diameter, depth, pinc=0., pdec=90., susc = susc, Einc=Eincd, Edec=Edecd, Bigrf=Bigrfd, x0=x0, Q=Q, rinc = rinc, rdec = rdec)
    p = definePrism()
    p.x0, p.y0, p.z0, p.dx, p.dy, p.dz = x0, 0., -depth, length, diameter, diameter
    p.susc,  p.pinc, p.pdec = susc, 0., 0.
    p.Binc, p.Bdec, p.Bigrf = Bincd, Bdecd, Bigrfd
    p.Q, p.rinc, p.rdec = Q, rinc, rdec

    nx, ny = 100, 1
    shape = (nx, ny)
    xLoc = np.linspace(xlim[0], xlim[1], nx)

    zLoc = np.ones(np.shape(xLoc))*rx_h
    yLoc = np.zeros(np.shape(xLoc))

    #xpl, ypl, zpl = fatiandoGridMesh.regular(surveyArea,shape, z=z)
    rxLoc = np.c_[Utils.mkvc(xLoc), Utils.mkvc(yLoc), Utils.mkvc(zLoc)]

    f = plt.figure(figsize = (10, 5))
    gs = gridspec.GridSpec(2, 1,height_ratios=[2,1])

    ax0 = plt.subplot(gs[0])
    ax1 = plt.subplot(gs[1])

    ax1.plot(x0, depth, 'ko')
    ax1.text(x0+0.5, depth, 'Rebar', color='k')
    ax1.text(xlim[0]+1.,-1.2, 'Magnetometer height (1.9 m)', color='b')
    ax1.plot(xlim, np.r_[-rx_h, -rx_h], 'b--')

    magi,magr = getField(p, rxLoc, 'bz', 'total')

    ax1.plot(xlim, np.r_[0., 0.], 'k--')
    ax1.set_xlim(xlim)
    ax1.set_ylim(-2.5, 2.5)

    ax0.scatter(loc,tfa,c=teams)
    ax0.errorbar(loc,tfa,yerr=std,linestyle = "None",color="k")
    ax0.set_xlim(xlim)
    ax0.grid(which="both")

    ax0.plot(xLoc, magi, 'b', label='induced')
    ax0.plot(xLoc, magr, 'r', label='remnant')
    ax0.plot(xLoc, magi+magr, 'k', label='total')
    ax0.legend(loc=2)
    # ax[1].plot(loc-8, magnT[::-1], )

    ax1.set_xlabel("Northing (m)")
    ax1.set_ylabel("Depth (m)")

    ax0.set_ylabel("Total field anomaly (nT)")

    ax0.grid(True)
    ax0.set_xlabel("Northing (m)")

    ax1.grid(True)
    ax1.set_xlabel("Northing (m)")

    ax1.invert_yaxis()

    plt.tight_layout()
    plt.show()

    return True


def plotObj3D(p, rx_h, elev, azim, npts2D, xylim,
              profile=None, x0=15., y0=0.):

    # define the survey area
    surveyArea = (-xylim, xylim, -xylim, xylim)
    shape = (npts2D, npts2D)

    xr = np.linspace(-xylim, xylim, shape[0])
    yr = np.linspace(-xylim, xylim, shape[1])
    X, Y = np.meshgrid(xr, yr)
    Z = np.ones(np.shape(X))*rx_h

    rxLoc = np.c_[Utils.mkvc(X), Utils.mkvc(Y), Utils.mkvc(Z)]

    depth = p.z0
    x1, x2 = p.xn[0], p.xn[1]
    y1, y2 = p.yn[0], p.yn[1]
    z1, z2 = p.zn[0], p.zn[1]
    pinc, pdec = p.pinc, p.pdec

    fig = plt.figure(figsize=(7, 7))
    ax = fig.add_subplot(111, projection='3d')
    plt.rcParams.update({'font.size': 13})

    ax.set_xlim3d(surveyArea[:2])
    ax.set_ylim3d(surveyArea[2:])
#     ax.set_zlim3d(depth+np.array(surveyArea[:2]))
    ax.set_zlim3d(-surveyArea[-1]*1.5, 3)

    # Create a rectangular prism, rotate and plot
    block_xyz = np.asarray([[x1, x1, x2, x2, x1, x1, x2, x2],
                           [y1, y2, y2, y1, y1, y2, y2, y1],
                           [z1, z1, z1, z1, z2, z2, z2, z2]])

    rot = Utils.mkvc(Utils.dipazm_2_xyz(pinc, pdec))

    xyz = Utils.rotatePointsFromNormals(block_xyz.T, rot, np.r_[0., 1., 0.],
                                        np.r_[p.xc, p.yc, p.zc])

    # Face 1
    ax.add_collection3d(Poly3DCollection([zip(xyz[:4, 0],
                                              xyz[:4, 1],
                                              xyz[:4, 2])]))

    # Face 2
    ax.add_collection3d(Poly3DCollection([zip(xyz[4:, 0],
                                              xyz[4:, 1],
                                              xyz[4:, 2])]))

    # Face 3
    ax.add_collection3d(Poly3DCollection([zip(xyz[[0, 1, 5, 4], 0],
                                              xyz[[0, 1, 5, 4], 1],
                                              xyz[[0, 1, 5, 4], 2])]))

    # Face 4
    ax.add_collection3d(Poly3DCollection([zip(xyz[[3, 2, 6, 7], 0],
                                              xyz[[3, 2, 6, 7], 1],
                                              xyz[[3, 2, 6, 7], 2])]))

    # Face 5
    ax.add_collection3d(Poly3DCollection([zip(xyz[[0, 4, 7, 3], 0],
                                              xyz[[0, 4, 7, 3], 1],
                                              xyz[[0, 4, 7, 3], 2])]))

    # Face 6
    ax.add_collection3d(Poly3DCollection([zip(xyz[[1, 5, 6, 2], 0],
                                              xyz[[1, 5, 6, 2], 1],
                                              xyz[[1, 5, 6, 2], 2])]))

    ax.set_xlabel('Easting (X; m)')
    ax.set_ylabel('Northing (Y; m)')
    ax.set_zlabel('Depth (Z; m)')
    # ax.invert_zaxis()
    ax.invert_yaxis()

    ax.plot(rxLoc[:, 0], rxLoc[:, 1], rxLoc[:, 2], '.g', alpha=0.1)

    if profile == "X":
        ax.plot(np.r_[surveyArea[:2]], np.r_[0., 0.], np.r_[rx_h, rx_h], 'r-')
    elif profile == "Y":
        ax.plot(np.r_[0., 0.], np.r_[surveyArea[2:]], np.r_[rx_h, rx_h], 'r-')
    elif profile == "XY":
        ax.plot(np.r_[0., 0.], np.r_[surveyArea[:2]], np.r_[rx_h, rx_h], 'r-')
        ax.plot(np.r_[surveyArea[2:]], np.r_[0., 0.], np.r_[rx_h, rx_h], 'r-')

    ax.view_init(elev, azim)
    plt.show()

    return True


def linefun(x1, x2, y1, y2, nx, tol=1e-3):
    dx = x2-x1
    dy = y2-y1

    if np.abs(dx) < tol:
        y = np.linspace(y1, y2, nx)
        x = np.ones_like(y)*x1
    elif np.abs(dy) < tol:
        x = np.linspace(x1, x2, nx)
        y = np.ones_like(x)*y1
    else:
        x = np.linspace(x1, x2, nx)
        slope = (y2-y1)/(x2-x1)
        y = slope*(x-x1)+y1
    return x, y


def plogMagSurvey2D(Box, susc, Einc, Edec, Bigrf, x1, y1, x2, y2, comp, irt,  Q, rinc, rdec):

    import matplotlib.gridspec as gridspec

    # Create a prism
    p = definePrism()
    p.dx, p.dy, p.dz = Box.kwargs['dx'], Box.kwargs['dy'], Box.kwargs['dz']
    p.z0, p.pinc, p.pdec = -Box.kwargs['depth'], Box.kwargs['pinc'], Box.kwargs['pdec']

    srvy = survey()
    srvy.rx_h, srvy.npts2D, srvy.xylim = Box.kwargs['rx_h'],Box.kwargs['npts2D'], Box.kwargs['xylim']
    # Create problem
    prob = problem()
    prob.prism = p
    prob.survey = srvy

    x, y = linefun(x1, x2, y1, y2, prob.survey.npts2D)
    xyz_line = np.c_[x, y, np.ones_like(x)*prob.survey.rx_h]

    fig = plt.figure(figsize=(18*1.5,3.4*1.5))
    plt.rcParams.update({'font.size': 14})
    gs1 = gridspec.GridSpec(2, 7)
    gs1.update(left=0.05, right=0.48, wspace=0.05)
    ax1 = plt.subplot(gs1[:2, :3])
    ax2 = plt.subplot(gs1[0, 4:])
    ax1.axis("equal")

    prob.Bdec, prob.Binc, prob.Bigrf = Edec, Einc, Bigrf
    prob.Q, prob.rinc, prob.rdec = Q, rinc, rdec
    prob.uType, prob.mType = comp, 'total'
    prob.susc = susc

    # Compute fields from prism
    b_ind, b_rem = prob.fields()

    if irt == 'total':
        out = b_ind + b_rem

    elif irt == 'induced':
        out = b_ind

    else:
        out = b_rem

    X, Y = np.meshgrid(prob.survey.xr, prob.survey.yr)

    dat = ax1.contourf(X,Y, np.reshape(out, (X.shape)).T, 25)
    cb = plt.colorbar(dat, ax=ax1, ticks=np.linspace(out.min(), out.max(), 5))
    cb.set_label("nT")
    ax1.plot(x,y, 'w.', ms=3)

    ax1.text(x[0], y[0], 'A', fontsize = 16, color='w')
    ax1.text(x[-1], y[-1], 'B', fontsize = 16, color='w')

    ax1.set_xlabel('Easting (X; m)')
    ax1.set_ylabel('Northing (Y; m)')
    ax1.set_xlim(X.min(), X.max())
    ax1.set_ylim(Y.min(), Y.max())
    ax1.set_title(irt+' '+comp)

    # Compute fields on the line
    #out_linei, out_liner = getField(p, xyz_line, comp, 'total')
    #out_linei = getField(p, xyz_line, comp,'induced')
    #out_liner = getField(p, xyz_line, comp,'remanent')

    #out_linet = out_linei+out_liner

    # distance = np.sqrt((x-x1)**2.+(y-y1)**2.)
    # ax2.plot(distance, out_linei, 'b.-')
    # ax2.plot(distance, out_liner, 'r.-')
    # ax2.plot(distance, out_linet, 'k.-')
    # ax2.set_xlim(distance.min(), distance.max())

    # ax2.set_xlabel("Distance (m)")
    # ax2.set_ylabel("Magnetic field (nT)")

    # ax2.text(distance.min(), out_linei.max()*0.8, 'A', fontsize = 16)
    # ax2.text(distance.max()*0.97, out_linei.max()*0.8, 'B', fontsize = 16)
    # ax2.legend(("induced", "remanent", "total"), bbox_to_anchor=(0.5, -0.3))
    # ax2.grid(True)
    # plt.show()

    return True


def fitlineRem():
    Q = widgets.interactive(profiledataRem, data=widgets.ToggleButtons(options=['MonSt','WedTA','WedSt']),\
             B0=widgets.FloatText(value=0.),\
             x0=widgets.FloatSlider(min=5., max=25., step=0.1, value=15.), \
             depth=widgets.FloatSlider(min=0.,max=2.,step=0.05,value=0.5), \
             susc=widgets.FloatSlider(min=0., max=800.,step=5., value=1.),\
             Q=widgets.FloatSlider(min=0., max=10.,step=0.1, value=0.),\
             rinc=widgets.FloatSlider(min=-180., max=180.,step=1., value=0.),\
             rdec=widgets.FloatSlider(min=-180., max=180.,step=1., value=0.),
             )
    return Q


def ViewMagSurvey2DInd(Box):


    def MagSurvey2DInd(susc, Einc, Edec, Bigrf, comp, irt, Q, rinc, rdec):

        # hardwire the survey line for now
        x1, x2, y1, y2 = -10., 10, 0., 0.

        return plogMagSurvey2D(Box, susc, Einc, Edec, Bigrf, x1, y1, x2, y2 , comp, irt, Q, rinc, rdec)

    out = widgets.interactive (MagSurvey2DInd 
                    ,susc=widgets.FloatSlider(min=0,max=200,step=0.1,value=0.1,continuous_update=False) \
                    #,susc=widgets.FloatText(value=1.) \
                    ,Einc=widgets.FloatSlider(min=-90.,max=90,step=5,value=90,continuous_update=False) \
                    ,Edec=widgets.FloatSlider(min=-90.,max=90,step=5,value=0,continuous_update=False) \
                    ,Bigrf=widgets.FloatSlider(min=54000.,max=55000,step=25,value=54500,continuous_update=False) \
                    ,comp=widgets.ToggleButtons(options=['tf','bx','by','bz'])
                    ,irt=widgets.ToggleButtons(options=['induced','remanent', 'total']) 
                    ,Q=widgets.FloatSlider(min=0.,max=10,step=1,value=0,continuous_update=False) \
                    ,rinc=widgets.FloatSlider(min=-90.,max=90,step=5,value=0,continuous_update=False) \
                    ,rdec=widgets.FloatSlider(min=-90.,max=90,step=5,value=0,continuous_update=False) \
                    )
    return out


def Prism(dx, dy, dz, depth, pinc, pdec, npts2D, xylim, rx_h, View_elev, View_azim):
    #p = definePrism(dx, dy, dz, depth,pinc=pinc, pdec=pdec, susc = 1., Einc=90., Edec=0., Bigrf=1e-6)
    p = definePrism()
    p.dx, p.dy, p.dz, p.z0 = dx, dy, dz, -depth
    p.pinc, p.pdec = pinc, pdec
    return plotObj3D(p, rx_h, View_elev, View_azim, npts2D, xylim, profile="X")


def ViewPrism(dx, dy, dz, depth):
    elev, azim = 20, 250
    npts2D, xylim = 20, 5.
    Q = widgets.interactive(Prism \
                            , dx=widgets.FloatSlider(min=1e-4, max=2., step=0.05, value=dx, continuous_update=False) \
                            , dy=widgets.FloatSlider(min=1e-4, max=2., step=0.05, value=dy, continuous_update=False) \
                            , dz=widgets.FloatSlider(min=1e-4, max=2., step=0.05, value=dz, continuous_update=False) \
                            , depth=widgets.FloatSlider(min=0., max=10., step=0.1, value=-depth, continuous_update=False)\
                            , pinc=(-90., 90., 10.) \
                            , pdec=(-90., 90., 10.) \
                            , npts2D=widgets.FloatSlider(min=5, max=100, step=5, value=npts2D, continuous_update=False) \
                            , xylim=widgets.FloatSlider(min=2, max=10, step=1, value=xylim, continuous_update=False) \
                            , rx_h=widgets.FloatSlider(min=0.1, max=2.5, step=0.1, value=rx_h, continuous_update=False) \
                            , View_elev=widgets.FloatSlider(min=-90, max=90, step=5, value=elev, continuous_update=False) \
                            , View_azim=widgets.FloatSlider(min=0, max=360, step=5, value=azim, continuous_update=False))

    return Q

# def PrismSurvey(dx, dy, dz, depth, pinc, pdec):
#     elev, azim = 20, 250
#     p = definePrism(dx, dy, dz, depth,pinc=pinc, pdec=pdec, susc = 1., Einc=90., Edec=0., Bigrf=1e-6)
#     return p, plotObj3D(p, elev, azim, profile=None, z=0., xmax=20, ymax=20)


# def ViewPrismSurvey(dx, dy, dz, depth):
#     Q = widgets.interactive(PrismSurvey,dx=widgets.FloatText(value=dx),dy=widgets.FloatText(value=dy), dz=widgets.FloatText(value=dz)\
#                     ,depth=widgets.FloatText(value=depth)
#                     ,pinc=(-90., 90., 10.), pdec=(-90., 90., 10.))
#     return Q
