#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov 13 17:44:36 2021

@author: amal
"""

import numpy as np
from scipy import integrate
from scipy.optimize.nonlin import newton_krylov
# import time
from mpi4py import MPI
from numba import njit

COMM = MPI.COMM_WORLD  # The default communicator
SIZE = COMM.Get_size() # The number of processes
RANK = COMM.Get_rank() # The rank of processes

''' inputs..............................................................................................................''' ## DONE
T=3.0 # horizon length 
N=1 # number of cars 
u_max=1.0 # free flow speed
rho_jam=1.0 # jam density
L=N # road length
CFL=0.75    # CFL<1
rho_a=0.05; rho_b=0.95; gama=0.1
# rho_a=0.2; rho_b=0.8; gama=0.15*L
# costf="LWR"
# """ Viscous solution"""
EPS=0.45
# viscosity coefficient
mu=0.0 # LWR
# mu=0.045 # Sep
# mu=0.03 # NonSep
""" grid discretization.................................................................................................. """  ## DONE
Nx=15; Nt=60 # Final spatial-temporal grid  
# Nx=30; Nt=120
# Nx=60; Nt=240
# Nx=120; Nt=480
# Nx=240; Nt=960
# Nx=480; Nt=1920 

dx=L/Nx # spatial step size
if mu==0.0:
    dt=min(T/Nt,(CFL*dx)/u_max) # temporal step size
    eps=0.0
else:
    dt=min(T/Nt,CFL*dx/abs(u_max),EPS*(dx**2)/mu) # temporal step size
    eps=mu*dt/(dx**2) # V
x=np.linspace(0,L,Nx+1)
# t=np.linspace(0,T,Nt+1)
t=np.arange(0,T+dt,dt)
Nt=len(t)-1
if RANK==0:
    print('Nx={Nx}, Nt={Nt}'.format(Nx=Nx,Nt=Nt))
    print('dx={dx}, dt={dt}'.format(dx=round(dx,4),dt=round(dt,4)))
    
guess0 = np.zeros(3*Nt*Nx+2*Nx) ## Done
########## LWR
# guess0=np.loadtxt('plots/lwr/PL_njit_Guess1_LWR_T3_N1.dat')
# guess0=np.loadtxt('plots/lwr/PL_njit_Guess2_LWR_T3_N1.dat')
# guess0=np.loadtxt('plots/lwr/PL_njit_Guess3_LWR_T3_N1.dat')
# guess0=np.loadtxt('plots/lwr/PL_njit_Guess4_LWR_T3_N1.dat')
# guess0=np.loadtxt('plots/lwr/PL_njit_Guess5_LWR_T3_N1.dat')
########## Separable
# guess0=np.loadtxt('plots/sep/PL_njit_Guess1_Sep_T3_N1.dat')
# guess0=np.loadtxt('plots/sep/PL_njit_Guess2_Sep_T3_N1.dat')
# guess0=np.loadtxt('plots/sep/PL_njit_Guess3_Sep_T3_N1.dat')
# guess0=np.loadtxt('plots/sep/PL_njit_Guess4_Sep_T3_N1.dat')
# guess0=np.loadtxt('plots/sep/PL_njit_Guess5_Sep_T3_N1.dat')
########## Non-Separable
# guess0=np.loadtxt('plots/nonsep/PL_njit_Guess1_NonSep_T3_N1.dat')
# guess0=np.loadtxt('plots/nonsep/PL_njit_Guess2_NonSep_T3_N1.dat')
# guess0=np.loadtxt('plots/nonsep/PL_njit_Guess3_NonSep_T3_N1.dat')
# guess0=np.loadtxt('plots/nonsep/PL_njit_Guess4_NonSep_T3_N1.dat')
# guess0=np.loadtxt('plots/nonsep/PL_njit_Guess5_NonSep_T3_N1.dat')
""" for MPI : Creates a division of processors in a cartesian grid.................................................... """ ## DONE
nbr_x=Nx+1; nbr_t=Nt+1 # spatial-temporal grid sizes 
nx=nbr_x-1; nt=nbr_t # number of points for MPI
px=int(np.sqrt(SIZE))-1 # number of processes on each line-1
pt=px # number of processes on each column-1
# print("px={px}, pt={pt}".format(px=px, pt=pt))
new_size=(px+1)*(pt+1) # the Number of processes to decompose 
# print('new_size=',new_size)
nbrx=int(nx/(px+1)) #number of points for px (except root)
nbrt=int(nt/(pt+1)) #number of points for pt (except root)
dims=[px+1,pt+1] # The array containing the number of processes to assign to each dimension
# print('dims=',dims)
npoints=[nx,nt]
# print('npoints=',npoints)

""" functions For MPI.................................................................................................. """ ## DONE

def create_2d_cart(): # return communicator (cart2d) with new cartesian topology
                                                                                                                                                                                                                                              
    periods = tuple([True, False]) # True : periodic, False : non-periodic Cartesian topology
    reorder = False # the rank of the processes in the new communicator (COMM_2D) is the same as in the old communicator (COMM). 
    
    # if (RANK == 0):
    #     print("Exécution avec",SIZE," MPI processes\n"
    #             "Taille du domaine : nx=",npoints[0], " nt=",npoints[1],"\n"
    #             "Dimension pour la topologie :",dims[0]," along x", dims[1]," along t\n"
    #             "-----------------------------------------") 

    cart2d = COMM.Create_cart(dims = dims, periods = periods, reorder = reorder)
    
    return cart2d

nb_neighbours = 4
N = 0 # hight
E = 1 # right
S = 2 # low
W = 3 # left

def create_neighbours(cart2d): # Find processor neighbors

    neighbour = np.zeros(nb_neighbours, dtype=np.int8)
    # Outputs : rank of source, destination processes
    neighbour[W],neighbour[E] = cart2d.Shift(direction=0,disp=1) # direction 0: <->
    neighbour[S],neighbour[N] = cart2d.Shift(direction=1,disp=1) # direction 1 : |
    
    # print("I am", RANK," my neighbours are : N", neighbour[N]," E",neighbour[E] ," S ",neighbour[S]," W",neighbour[W])

    return neighbour

def Coords_2D(cart2d):

    coord2d = cart2d.Get_coords(RANK)
    # print("I’m rank :",RANK," my 2d coords are",coord2d)
    
    sy = int((coord2d[1] * npoints[1]) / dims[1]) + 1
    
    sx = int((coord2d[0] * npoints[0]) / dims[0]) + 1

    ex = int(((coord2d[0] + 1) * npoints[0]) / dims[0])
    ey = int(((coord2d[1] + 1) * npoints[1]) / dims[1])

    # print("Rank in the topology :",RANK," Local Grid Index :", sx, " to ",ex," along x, ",
    #       sy, " to", ey," along t")
    
    return coord2d, sx, ex, sy, ey


def create_derived_type(sx, ex, sy, ey): 
    
    '''Creation of the type_line derived datatype to exchange points
     with northern to southern neighbours '''
    ## Row of a matrix is not contiguous in memory
    ## In N x M matrix, each element of a row is separated by N elements
    type_ligne = MPI.DOUBLE.Create_contiguous(ey-sy + 1) # count = N = ey-sy + 1
    type_ligne.Commit() # A new datatype must be committed before using it
    
    '''Creation of the type_column derived datatype to exchange points
     with western to eastern neighbours '''
    ## A vector type describes a series of blocks, all of equal size (blocklen), spaced with a constant stride.
    ## In N x M matrix, N= and M=block_count
    # block_count : The number of blocks to create.
    # blocklen : The number of (same) elements in each block
    # stride : Distance between the start of each block, expressed in number of elements.
    type_column = MPI.DOUBLE.Create_vector(ex-sx + 3, 1, ey-sy + 3) # block_count = ex-sx + 1 ; blocklen = 1 ; stride = ey-sy + 3
    type_column.Commit()

    return type_ligne, type_column

@njit(fastmath=True)
def IDX(i, j): 
        return ( ((i)-(sx-1))*(ey-sy+3) + (j)-(sy-1) )

def communications(u, sx, ex, sy, ey, type_column, type_ligne):

    #[data, count, datatype]
    ''' Envoyer au voisin W et recevoir du voisin E '''#type_ligne
    COMM.Send([u[IDX(sx, sy) : ], 1, type_ligne], dest=neighbour[W]) #IDX(sx, sy)XX
    COMM.Recv([u[IDX(ex+1, sy) : ], 1, type_ligne], source=neighbour[E]) #IDX(ex, sy+1)XX ,,, IDX(ex+1, sy)

    ''' Envoyer au voisin E et recevoir du voisin W '''#type_ligne
    COMM.Send([u[IDX(ex, sy) : ], 1, type_ligne], dest=neighbour[E]) #IDX(ex, sy)XX
    COMM.Recv([u[IDX(sx-1, sy) : ], 1, type_ligne], source=neighbour[W]) #IDX(sx, sy-1)XX

    ''' Envoyer au voisin S et recevoir du voisin N '''#type_column
    COMM.Send([u[IDX(sx-1, sy) : ], 1, type_column], dest=neighbour[S]) #IDX(sx, sy)XX
    COMM.Recv([u[IDX(sx-1, ey+1) : ], 1, type_column], source=neighbour[N]) #IDX(sx+1, ey)XX

    ''' Envoyer au voisin N et recevoir du voisin S ''' #type_column
    COMM.Send([u[IDX(sx-1, ey) : ], 1, type_column], dest=neighbour[N]) #IDX(sx, ey)XX
    COMM.Recv([u[IDX(sx-1, sy-1) : ], 1, type_column], source=neighbour[S]) #IDX(sx-1, sy)XX ,,,, IDX(sx, sy-1)
    
    return 0


cart2D=create_2d_cart() ## Done
neighbour = create_neighbours(cart2D) ## Done
coord2D, sx, ex, sy, ey = Coords_2D(cart2D) ## Done
type_ligne, type_column = create_derived_type(sx, ex, sy, ey) ## Done

""" Initialization................................................................................................ """ ## DONE

@njit(fastmath=True)
def r_id(j,n): ## Done
    return (j-1)*(Nt+1)+n
@njit(fastmath=True)
def u_id(j,n): ## Done
    return (Nt+1)*Nx+(j-1)*Nt+n
@njit(fastmath=True)
def V_id(j,n): ## Done
    return (2*Nt+1)*Nx+(j-1)*(Nt+1)+n
@njit(fastmath=True)
def to_solution(Nx,Nt,sol,rho,u,V): 
    for j in range(1,Nx+1):
        for n in range(0,Nt):
            rho[j,n]=sol[r_id(j,n)]
            u[j,n]=sol[u_id(j,n)]
            V[j,n]=sol[V_id(j,n)]
        rho[j,Nt]=sol[r_id(j,Nt)]
        V[j,Nt]=sol[V_id(j,Nt)]
    return 0
@njit(fastmath=True)
def solution_to(Nx,Nt,sol,rho,u,V): 
    for j in range(1,Nx+1):
        for n in range(0,Nt):
            sol[r_id(j,n)]=rho[j,n]
            sol[u_id(j,n)]=u[j,n]
            sol[V_id(j,n)]=V[j,n]
        sol[r_id(j,Nt)]=rho[j,Nt]
        sol[V_id(j,Nt)]=V[j,Nt]
    return 0

rho0=np.zeros((Nx+1,Nt+1))  ## Done
u0=np.zeros((Nx+1,Nt+1))  ## Done
V0=np.zeros((Nx+1,Nt+1))  ## Done
to_solution(Nx,Nt,guess0,rho0,u0,V0)  ## Done
# if RANK==0:
#     print('guess0=',guess0)
#     print('rho0=',rho0)
#     print('u0=',u0)
#     print('V0=',V0)

f_rho=rho0.copy()
f_u=u0.copy()
f_V=V0.copy()
@njit(fastmath=True)
def initialization(rho0, u0, V0, sx, ex, sy, ey):  
    
    SIZE = (ex-sx+3) * (ey-sy+3)
    
    rho       = np.zeros(SIZE)
    u       = np.zeros(SIZE)
    V   = np.zeros(SIZE)
    
    '''Initialization of rho, u et V '''
    for i in range(sx, ex+1): # x axis
        for j in range(sy, ey+1): # y axis
        
            rho[IDX(i, j)] = rho0[i,j-1]
            u[IDX(i, j)] = u0[i,j-1]
            V[IDX(i, j)] = V0[i,j-1]
                   
    # print("I’m rank :",RANK, "sx",sx,"ex",ex, "sy",sy, "ey",ey," new_rho",rho)
            
    return rho, u, V

rho, u, V = initialization(rho0, u0, V0, sx, ex, sy, ey) ## Done
# print("rank",RANK,"len(rho)",len(rho),"len(u)",len(u),"len(V)",len(V))
# if RANK==3:
#     print('rho=',rho)
#     print('u=',u)
#     print('V=',V)
@njit(fastmath=True)    
def r_idx(j,n): 
    return (j-(sx-1))*w_nby+(n-(sy-1))
@njit(fastmath=True)
def u_idx(j,n): 
    return w_nby*w_nbx+(j-(sx-1))*w_nby+(n-(sy-1))
@njit(fastmath=True)
def V_idx(j,n): 
    return 2*w_nby*w_nbx+(j-(sx-1))*w_nby+(n-(sy-1))
@njit(fastmath=True)    
def to_sol(sol,rho,u,V): 
    for j in range(sx-1,ex+2):
        for n in range(sy-1,ey+2):
            sol[r_idx(j,n)]=rho[IDX(j,n)]
            sol[u_idx(j,n)]=u[IDX(j,n)]
            sol[V_idx(j,n)]=V[IDX(j,n)]
    return 0
@njit(fastmath=True)
def sol_to(sol,rho,u,V): 
    for j in range(sx-1,ex+2):
        for n in range(sy-1,ey+2):
            rho[IDX(j,n)]=sol[r_idx(j,n)]
            u[IDX(j,n)]=sol[u_idx(j,n)]
            V[IDX(j,n)]=sol[V_idx(j,n)]
    return 0
@njit(fastmath=True)
def r_idx_loc(j,n): 
        return (j-j0)*(F_nby+1)+(n-n0)
@njit(fastmath=True)
def u_idx_loc(j,n): 
    return (F_nby+1)*F_nbx+(j-j0)*F_nby+(n-n0)
@njit(fastmath=True)
def V_idx_loc(j,n): 
    return 2*F_nby*F_nbx+F_nbx+(j-j0)*(F_nby+1)+(n-n0)
@njit(fastmath=True)
def global_to_local(local_sol,global_sol):  ### Done
    for j in range(j0,F_Nx+1):
        for n in range(n0,F_Nt+1):
            local_sol[r_idx_loc(j,n)]=global_sol[r_idx(j,n)]
            if n!=F_Nt:
                local_sol[u_idx_loc(j,n)]=global_sol[u_idx(j,n)]
            local_sol[V_idx_loc(j,n)]=global_sol[V_idx(j,n)]
    return 0
@njit(fastmath=True)
def local_sol_to(sol,rho,u,V):  ###?
        for j in range(j0,F_Nx+1):
            for n in range(n0,F_Nt+1):
                rho[IDX(j,n)]=sol[r_idx_loc(j,n)]
                if n!=F_Nt:
                    u[IDX(j,n)]=sol[u_idx_loc(j,n)]
                V[IDX(j,n)]=sol[V_idx_loc(j,n)]
        return 0
    
''' MFG functions....................................................................................................... ''' ## DONE
@njit(fastmath=True)
def U(rho): # Greenshields desired speed
    return u_max*(1-rho/rho_jam)
@njit(fastmath=True)
def f_mfg_LWR(u,r):
    return 0.5*((U(r)-u)**2) # MFG-LWR
@njit(fastmath=True)
def f_mfg_Sep(u,r):
    return 0.5*((u/u_max)**2)-(u/u_max)+(r/rho_jam) # MFG-Separable
@njit(fastmath=True)
def f_mfg_NonSep(u,r):
    return 0.5*((u/u_max)**2)-(u/u_max)+((u*r)/(u_max*rho_jam)) # MFG-NonSeparable
@njit(fastmath=True)
def f_star_p_LWR(p,r): # 0<=u<=u_max
    return U(r)-p # MFG-LWR
@njit(fastmath=True)
def f_star_p_Sep(p,r): # 0<=u<=u_max
    return max(min(u_max*(1-p*u_max),u_max),0) # MFG-Separable
@njit(fastmath=True)    
def f_star_p_NonSep(p,r): # 0<=u<=u_max
    return max(min(u_max*(1-r/rho_jam-u_max*p),u_max),0) # MFG-NonSeparable
@njit(fastmath=True)    
def f_star_LWR(p,r): # p=Vx
    return -0.5*(p**2)+U(r)*p # MFG-LWR
@njit(fastmath=True)    
def f_star_Sep(p,r): # p=Vx
    return f_star_p_Sep(p,r)*p+f_mfg_Sep(f_star_p_Sep(p,r),r) # MFG-Separable
@njit(fastmath=True)    
def f_star_NonSep(p,r): # p=Vx
    return f_star_p_NonSep(p,r)*p+f_mfg_NonSep(f_star_p_NonSep(p,r),r) # MFG-NonSeparable

def integral(a,b): 
    x2 = lambda x: rho_int(x)
    I=integrate.quad(x2, a, b)
    return I[0]

@njit(fastmath=True)
def rho_int(s): # initial density
    return rho_a+(rho_b-rho_a)*np.exp(-0.5*((s-0.5*L)/gama)**2) # 0<=rho<=rho_jam
@njit(fastmath=True)
def VT(a): # Terminal cost
    return 0.0
@njit(fastmath=True)
def Fr_idx_loc(j,n): 
        return (j-j0)*F_nby+(n-n0)
@njit(fastmath=True)
def Fu_idx_loc(j,n): 
    return F_nby*F_nbx+(j-j0)*F_nby+(n-n0)
@njit(fastmath=True)
def FV_idx_loc(j,n): 
    return 2*F_nby*F_nbx+(j-j0)*F_nby+(n-n0)
@njit(fastmath=True)
def Frint_idx_loc(j):
    return 3*F_nby*F_nbx+(j-j0)
@njit(fastmath=True)
def FVter_idx_loc(j):
    return 3*F_nby*F_nbx+F_nbx+(j-j0)
# @njit(fastmath=True)
def F(wloc,w,f_star_p,f_star): 
    # FF=[F_rho,F_u,F_V,F_rho_int,F_V_ter]
    FF=np.zeros(3*F_nby*F_nbx+2*F_nbx)
    for n in range(n0,F_Nt):
        for j in range(j0+1,F_Nx):
            # F_rho , F[0]->F[F_nby*F_nbx-1] ************ 2 
            FF[Fr_idx_loc(j,n)]=wloc[r_idx_loc(j,n+1)]-0.5*(wloc[r_idx_loc(j-1,n)]+wloc[r_idx_loc(j+1,n)])\
                +(0.5*dt/dx)*(wloc[r_idx_loc(j+1,n)]*wloc[u_idx_loc(j+1,n)]-wloc[r_idx_loc(j-1,n)]*wloc[u_idx_loc(j-1,n)])
            # F_u , F[F_nby*F_nbx]->F[2*F_nby*F_nbx-1] *********** 5
            FF[Fu_idx_loc(j,n)]=wloc[u_idx_loc(j,n)]-f_star_p((wloc[V_idx_loc(j,n+1)]-wloc[V_idx_loc(j-1,n+1)])/dx,wloc[r_idx_loc(j,n)])
            # F_V , F[2*F_nby*F_nbx]->F[3*F_nby*F_nbx-1] ********* 8 
            FF[FV_idx_loc(j,n)]=wloc[V_idx_loc(j,n+1)]-wloc[V_idx_loc(j,n)]\
                +dt*f_star((wloc[V_idx_loc(j,n+1)]-wloc[V_idx_loc(j-1,n+1)])/dx,wloc[r_idx_loc(j,n)])\
                    +eps*(wloc[V_idx_loc(j+1,n+1)]-2*wloc[V_idx_loc(j,n+1)]+wloc[V_idx_loc(j-1,n+1)])
    
        # F_rho , F[0]->F[F_nby*F_nbx-1] ************ 1 
        FF[Fr_idx_loc(j0,n)]=wloc[r_idx_loc(j0,n+1)]-0.5*(w[r_idx(j0-1,n)]+wloc[r_idx_loc(j0+1,n)])\
            +(0.5*dt/dx)*(wloc[r_idx_loc(j0+1,n)]*wloc[u_idx_loc(j0+1,n)]-w[r_idx(j0-1,n)]*w[u_idx(j0-1,n)])
        # F_u , F[F_nby*F_nbx]->F[2*F_nby*F_nbx-1] *********** 4 
        FF[Fu_idx_loc(j0,n)]=wloc[u_idx_loc(j0,n)]-f_star_p((wloc[V_idx_loc(j0,n+1)]-w[V_idx(j0-1,n+1)])/dx,wloc[r_idx_loc(j0,n)])
        # F_V , F[2*F_nby*F_nbx]->F[3*F_nby*F_nbx-1] ********* 7 
        FF[FV_idx_loc(j0,n)]=wloc[V_idx_loc(j0,n+1)]-wloc[V_idx_loc(j0,n)]\
            +dt*f_star((wloc[V_idx_loc(j0,n+1)]-w[V_idx(j0-1,n+1)])/dx,wloc[r_idx_loc(j0,n)])\
                +eps*(wloc[V_idx_loc(j0+1,n+1)]-2*wloc[V_idx_loc(j0,n+1)]+w[V_idx(j0-1,n+1)])
    
        # F_rho , F[0]->F[F_nby*F_nbx-1] ************ 3 
        FF[Fr_idx_loc(F_Nx,n)]=wloc[r_idx_loc(F_Nx,n+1)]-0.5*(wloc[r_idx_loc(F_Nx-1,n)]+w[r_idx(F_Nx+1,n)])\
            +(0.5*dt/dx)*(w[r_idx(F_Nx+1,n)]*w[u_idx(F_Nx+1,n)]-wloc[r_idx_loc(F_Nx-1,n)]*wloc[u_idx_loc(F_Nx-1,n)])
        # F_u , F[F_nby*F_nbx]->F[2*F_nby*F_nbx-1] *********** 6 
        FF[Fu_idx_loc(F_Nx,n)]=wloc[u_idx_loc(F_Nx,n)]-f_star_p((wloc[V_idx_loc(F_Nx,n+1)]-wloc[V_idx_loc(F_Nx-1,n+1)])/dx,wloc[r_idx_loc(F_Nx,n)])
        # F_V , F[2*F_nby*F_nbx]->F[3*F_nby*F_nbx-1] ********* 9 
        FF[FV_idx_loc(F_Nx,n)]=wloc[V_idx_loc(F_Nx,n+1)]-wloc[V_idx_loc(F_Nx,n)]\
            +dt*f_star((wloc[V_idx_loc(F_Nx,n+1)]-wloc[V_idx_loc(F_Nx-1,n+1)])/dx,wloc[r_idx_loc(F_Nx,n)])\
                +eps*(w[V_idx(F_Nx+1,n+1)]-2*wloc[V_idx_loc(F_Nx,n+1)]+wloc[V_idx_loc(F_Nx-1,n+1)])
                
    for j in range(j0,F_Nx+1):    
        # F_rho_int , F[3*F_nby*F_nbx]->F[3*F_nby*F_nbx+F_nbx-1] ********** 10
        if n0==sy:
            FF[Frint_idx_loc(j)]=wloc[r_idx_loc(j,n0)]-(1/dx)*integral(x[j-1],x[j])
        if n0==sy-1:
            FF[Frint_idx_loc(j)]=wloc[r_idx_loc(j,n0)]-w[r_idx(j,n0)]
        # F_V_ter , F[3*F_nby*F_nbx+F_nbx]->F[3*F_nby*F_nbx+2*F_nbx-1] ********* 11
        if F_Nt==ey:
            FF[FVter_idx_loc(j)]=wloc[V_idx_loc(j,F_Nt)]-VT(x[j])
        if F_Nt==ey+1:
            FF[FVter_idx_loc(j)]=wloc[V_idx_loc(j,F_Nt)]-w[V_idx(j,F_Nt)]
            
    return FF
    
     
# t0 = time.process_time()   ###
# Pl_F_guess=F(wloc)
# t1 = time.process_time()   ###
# print("Time spent :",t1-t0)
# np.savetxt('Pl_F_guess.dat', Pl_F_guess)
@njit(fastmath=True)    
def jacobian(wloc): # Ignoring the forward-backward coupling  parts 
    # print(wloc)
    # J=np.zeros((3*F_nby*F_nbx+2*F_nbx,3*F_nby*F_nbx+2*F_nbx))
    row = []; col = []; data = []
    for j in range(j0,F_Nx+1):
        for n in range(n0,F_Nt):
            # J[Fr_idx_loc(j,n),r_idx_loc(j,n+1)]=1 # F_rho - rho ## Ok
            row.append(Fr_idx_loc(j,n)); col.append(r_idx_loc(j,n+1)); data.append(1)
            # J[Fu_idx_loc(j,n),u_idx_loc(j,n)]=1 # F_u - u  ## Ok
            row.append(Fu_idx_loc(j,n)); col.append(u_idx_loc(j,n)); data.append(1)
            # J[FV_idx_loc(j,n),V_idx_loc(j,n)]=-1 # F_V - V## Ok
            row.append(FV_idx_loc(j,n)); col.append(V_idx_loc(j,n)); data.append(-1)
            # J[FV_idx_loc(j,n),V_idx_loc(j,n+1)]=1-2*eps # F_V - V  ## Ok
            row.append(FV_idx_loc(j,n)); col.append(V_idx_loc(j,n+1)); data.append(1-2*eps)
            
            if j!=j0:
                # J[Fr_idx_loc(j,n),r_idx_loc(j-1,n)]=-(0.5*dt/dx)*wloc[u_idx_loc(j-1,n)]-0.5 # F_rho -rho  ## Ok
                row.append(Fr_idx_loc(j,n)); col.append(r_idx_loc(j-1,n)); data.append(-(0.5*dt/dx)*wloc[u_idx_loc(j-1,n)]-0.5)
                # J[Fr_idx_loc(j,n),u_idx_loc(j-1,n)]=-(0.5*dt/dx)*wloc[r_idx_loc(j-1,n)] # F_rho - u  ## Ok
                row.append(Fr_idx_loc(j,n)); col.append(u_idx_loc(j-1,n)); data.append(-(0.5*dt/dx)*wloc[r_idx_loc(j-1,n)])
                # J[FV_idx_loc(j,n),V_idx_loc(j-1,n+1)]=eps # F_V - V  ## Ok
                row.append(FV_idx_loc(j,n)); col.append(V_idx_loc(j-1,n+1)); data.append(eps)
            if j!=F_Nx:
                # J[Fr_idx_loc(j,n),r_idx_loc(j+1,n)]=(0.5*dt/dx)*wloc[u_idx_loc(j+1,n)]-0.5 # F_rho -rho ## Ok
                row.append(Fr_idx_loc(j,n)); col.append(r_idx_loc(j+1,n)); data.append((0.5*dt/dx)*wloc[u_idx_loc(j+1,n)]-0.5)
                # J[Fr_idx_loc(j,n),u_idx_loc(j+1,n)]=(0.5*dt/dx)*wloc[r_idx_loc(j+1,n)] # F_rho - u  ## Ok
                row.append(Fr_idx_loc(j,n)); col.append(u_idx_loc(j+1,n)); data.append((0.5*dt/dx)*wloc[r_idx_loc(j+1,n)])
                # J[FV_idx_loc(j,n),V_idx_loc(j+1,n+1)]=eps # F_V - V  ## Ok 
                row.append(FV_idx_loc(j,n)); col.append(V_idx_loc(j+1,n+1)); data.append(eps)
        # J[Frint_idx_loc(j),r_idx_loc(j,n0)]=1 # F_rho_int - rho ## Ok
        row.append(Frint_idx_loc(j)); col.append(r_idx_loc(j,n0)); data.append(1)
        # J[FVter_idx_loc(j),V_idx_loc(j,F_Nt)]=1 # F_V_ter - V  ## Ok
        row.append(FVter_idx_loc(j)); col.append(V_idx_loc(j,F_Nt)); data.append(1)
    
    # return J
    return row, col, data

from scipy.sparse import csc_matrix
import scipy.sparse.linalg as spla
def get_preconditioner(wloc):
    # Jac=jacobian(wloc)
    row, col, data =jacobian(wloc)
    shap=(3*F_nby*F_nbx+2*F_nbx,3*F_nby*F_nbx+2*F_nbx)
    # M=np.linalg.inv(Jac)
    # Jac1 = csc_matrix(Jac)
    Jac1 = csc_matrix((data, (row, col)),shape = shap)
    J_ilu = spla.spilu(Jac1)
    M_x = lambda r: J_ilu.solve(r)
    M = spla.LinearOperator(shap, M_x)
    
    return M
    

''' Calcul of global erreur............................................................................................. '''
@njit(fastmath=True)
def global_error(sol, sol_new): 
   
    local_error = 0
     
    for i in range(3*F_nbx*F_nby+2*F_nbx):
        temp = np.fabs( sol[i] - sol_new[i]  )
        if local_error < temp:
            local_error = temp;
    
    return local_error
        

""" Solve in grid (Nx,Nt)................................................................................................ """

rho_new = rho.copy() 
u_new = u.copy() 
V_new = V.copy()

w_nbx=ex-sx+3 ## Done
w_nby=ey-sy+3 ## Done
# guess_glob=np.zeros(3*w_nbx*w_nby) ## Done
j0=sx; F_Nx=ex  
if coord2D[1]==0:
    n0=sy
else:
    n0=sy-1
if coord2D[1]==pt:
    F_Nt=ey
else:
    F_Nt=ey+1
F_nbx=F_Nx-j0+1
F_nby=F_Nt-n0
# guess_loc=np.zeros(3*F_nbx*F_nby+2*F_nbx)


''' Stepping time.......................................................... '''
it = 0
convergence = False
it_max = 1000
# it_max=1
epsilon = 2.e-05

''' spend time................................................... '''
t1 = MPI.Wtime()
while (not(convergence) and (it < it_max)):
    it = it+1;

    rho_temp = rho.copy() 
    u_temp = u.copy() 
    V_temp = V.copy() 
    rho = rho_new.copy()
    u = u_new.copy() 
    V = V_new.copy() 
    rho_new = rho_temp.copy()
    u_new = u_temp.copy()
    V_new = V_temp.copy() 
        
    
    ''' Échange des interfaces à la n itération '''
    communications(rho, sx, ex, sy, ey, type_column, type_ligne) ## Done
    communications(u, sx, ex, sy, ey, type_column, type_ligne) ## Done
    communications(V, sx, ex, sy, ey, type_column, type_ligne) ## Done
    # if RANK==0:
    #     print('rho=',rho)
    # print(RANK,'V=',V)
     
    '''Calcul de rho_new, u_new et V_new à l’itération n 1 '''
    
    '''  Global guess '''
    guess_glob=np.zeros(3*w_nbx*w_nby) ## Done
    to_sol(guess_glob,rho,u,V) ## Done
    # print(RANK,guess_glob,V)
    # if RANK==0:
        # print(w_nbx,w_nby,len(rho),len(u),len(V),len(guess_glob))
        # print('guess_glob=',guess_glob)
        
    
    '''  Local guess, Local F => Local solution '''
    guess_loc=np.zeros(3*F_nbx*F_nby+2*F_nbx)
    global_to_local(guess_loc,guess_glob) # Done
    # np.savetxt('guess_loc.dat', guess_loc)
    # np.savetxt('guess_glob.dat', guess_glob)
    # if RANK==3:
    #     print('guess_loc=',guess_loc)
    
    ''' Solve with Newton-GMRES solver'''
    # t0 = time.process_time()   ###
    M=get_preconditioner(guess_loc)
    # t1 = time.process_time()   ###
    # print("Iteration", it,"Time spent (preconditionner) :",t1-t0)
    F_loc = lambda x : F(x,guess_glob,f_star_p_LWR,f_star_LWR)  
    # F_loc = lambda x : F(x,guess_glob,f_star_p_Sep,f_star_Sep)
    # F_loc = lambda x : F(x,guess_glob,f_star_p_NonSep,f_star_NonSep)
    # t0 = time.process_time()   ###
    sol_loc= newton_krylov(F_loc, guess_loc, method='gmres', verbose=0, inner_M=M) # verbose=1  , x_rtol=2e-12
    # t1 = time.process_time()   ###
    # print("Time spent (gmres) :",t1-t0)
    
    local_sol_to(sol_loc,rho_new,u_new,V_new)
    # if RANK==0:
    #     print('rho_new=',rho_new)
    
    ''' Computation of the global error '''
    local_error = global_error(guess_loc, sol_loc);
    diffnorm = COMM.allreduce(np.array(local_error), op=MPI.MAX )  
    # print(RANK,local_error)
       
    ''' Stop if we got the precision of the machine '''
    convergence = (diffnorm < epsilon) 
    
    ''' Print diffnorm for processor 0 '''
    # if ((RANK == 0) and ((it % 100) == 0)):
    if (RANK == 0):
        print("Iteration", it, " global_error = ", diffnorm);
        
''' temps écoulé...................................................................... '''
t2 = MPI.Wtime()

if (RANK == 0):
    ''' Print convergence time for processor 0 '''
    print("convergence après:",it, 'iterations in', t2-t1,'secs')
    
# if RANK==0:
#     print(rho_new.shape,rho_new)
    
# print(RANK,f_rho.shape,f_rho)
r_recvbuf = COMM.gather(rho_new, root=0)
u_recvbuf = COMM.gather(u_new, root=0)
V_recvbuf = COMM.gather(V_new, root=0)
j0_recvbuf=COMM.gather(sx, root=0)
jf_recvbuf=COMM.gather(ex, root=0)
n0_recvbuf=COMM.gather(sy, root=0)
nf_recvbuf=COMM.gather(ey, root=0)



if RANK==0:
    for rk in range(new_size):
        def IDX2(i, j): 
            return ( (i)*(nf_recvbuf[rk]-n0_recvbuf[rk]+3) + (j) )
        ro=r_recvbuf[rk]
        uu=u_recvbuf[rk]
        VV=V_recvbuf[rk]
        for j in range(j0_recvbuf[rk], jf_recvbuf[rk]+1): # x axis
            for n in range(n0_recvbuf[rk], nf_recvbuf[rk]+1): # y axis
                f_rho[j,n-1]=ro[IDX2(j-j0_recvbuf[rk]+1, n-n0_recvbuf[rk]+1)]
                f_u[j,n-1]=uu[IDX2(j-j0_recvbuf[rk]+1, n-n0_recvbuf[rk]+1)]
                f_V[j,n-1]=VV[IDX2(j-j0_recvbuf[rk]+1, n-n0_recvbuf[rk]+1)]
        
    final_solu=np.zeros(3*Nt*Nx+2*Nx)
    solution_to(Nx,Nt,final_solu,f_rho,f_u,f_V)
    # print(Nx,Nt,final_solu.shape)
    
    ############## LWR
    # np.savetxt('plots/lwr/PL_njit_Sol0_LWR_T3_N1.dat', final_solu)
    # np.savetxt('plots/lwr/PL_njit_Sol1_LWR_T3_N1.dat', final_solu)
    # np.savetxt('plots/lwr/PL_njit_Sol2_LWR_T3_N1.dat', final_solu)
    # np.savetxt('plots/lwr/PL_njit_Sol3_LWR_T3_N1.dat', final_solu)
    # np.savetxt('plots/lwr/PL_njit_Sol4_LWR_T3_N1.dat', final_solu)
    # np.savetxt('plots/lwr/PL_njit_Sol5_LWR_T3_N1.dat', final_solu)
    ############## Separable
    # np.savetxt('plots/sep/PL_njit_Sol0_Sep_T3_N1.dat', final_solu)
    # np.savetxt('plots/sep/PL_njit_Sol1_Sep_T3_N1.dat', final_solu)
    # np.savetxt('plots/sep/PL_njit_Sol2_Sep_T3_N1.dat', final_solu)
    # np.savetxt('plots/sep/PL_njit_Sol3_Sep_T3_N1.dat', final_solu)
    # np.savetxt('plots/sep/PL_njit_Sol5_Sep_T3_N1.dat', final_solu)
    ############## Non-Separable
    # np.savetxt('plots/nonsep/PL_njit_Sol0_NonSep_T3_N1.dat', final_solu)
    # np.savetxt('plots/nonsep/PL_njit_Sol1_NonSep_T3_N1.dat', final_solu)
    # np.savetxt('plots/nonsep/PL_njit_Sol2_NonSep_T3_N1.dat', final_solu)
    # np.savetxt('plots/nonsep/PL_njit_Sol3_NonSep_T3_N1.dat', final_solu)
    # np.savetxt('plots/nonsep/PL_njit_Sol5_NonSep_T3_N1.dat', final_solu)




























