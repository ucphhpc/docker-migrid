# -*- coding: utf-8 -*-
"""
Model functions used in optimization and functions used in visualization/testing
import matplotlib.pyplot as plt
"""
import numpy as np
import torch
import math
# import torch.nn.functional as F
# import time

import scipy.special


import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)



##########






#########

##NEW with scale factor: ......IDENTICAL result, but sigma_b now out of it
def sample_from_p_tx(N, width_factor, I1, I2):
    '''Use Uniform distribution to sample tau ~ d(tau)
    M: number of samples
    width_factor: determines range of tau (intensity values), in number of sigma_bs
    returns: samples tau'''

    #limit range (on z axis (voxels))
    #A=1/(2*width_factor*sigma_b)
    #U_range=torch.tensor([-width_factor*sigma_b, width_factor*sigma_b])*A ##!!


    U_range=torch.tensor([-0.5, 0.5]) ##!!

    #draw M samples form Uniform dist
    u = torch.distributions.Uniform(torch.ones(N)*U_range[0], torch.ones(N)*U_range[1]).sample()
    #u = torch.distributions.Uniform(torch.ones(M)*(-1), torch.ones(M)*1).sample()


    #transform from u to p(tx) distribution: using inverse p(tx)
    tx = (torch.erf(u*math.sqrt(2)*width_factor) + 1)*0.5*(I2-I1) + I1
    return tx

#
# def G(x, I1, I2, sigma_b):
#     arc=((I2-I1)/torch.sqrt(2*math.pi*sigma_b**2))*torch.exp(-( torch.erfinv( (  (2*x-2*I1)/(I2-I1) -1 ) )**2))
#     #remove NaN outside I-range - put 0 (MUST PUT SOMETHING SLIGHTLY LARGER THAN = TO AVOIN NAN.......)
#     #arc[torch.isnan(arc)] = torch.tensor(1E-10)#.double()
#     return arc
#
def G(x, I1, I2, sigma_b):
    arc=((I2-I1)/torch.sqrt(2*math.pi*sigma_b**2))*torch.exp(-( torch.erfinv( (  (2*x-2*I1)/(I2-I1) -1 ) )**2))
    #remove NaN outside I-range - put 0 (MUST PUT SOMETHING SLIGHTLY LARGER THAN = TO AVOIN NAN.......)
    #arc[torch.isnan(arc)] = torch.tensor(1E-10)#.double()
    return arc



# def log_p_tx(tx, I1, I2, sigma_b):

#     out= torch.log(sigma_b) + 0.5*math.log(2*math.pi) - torch.log(I2-I1) \
# +(torch.erfinv(  2*(tx-I1)/(I2-I1)  - 1) )**2

#     return out

def log_p_x_cond_tx(x, tx, sigma_n):
    return -torch.log(sigma_n) -0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2


def log_p_y_cond_tx(y, tx, I1, I2, sigma_b, sigma_n):

    G_=G(tx, I1, I2, sigma_b)
    exp_scaled_bessel_term = exp_scaled_modified_bessel(2*y*G_/(sigma_n**2), 0.5)

    out = math.log(2) -2*torch.log(sigma_n) + (3/2)*torch.log(y) - 0.5*torch.log(G_) \
    + torch.log(exp_scaled_bessel_term) + (2*y*G_/sigma_n**2)  -(y**2+G_**2)/sigma_n**2 #!!! log utanpå besselterm alone

    return out

#log_MC_uniform_int_p_x_y(x, y, N, width_factor, I1, I2, sigma_b, sigma_n)

def log_p_x_y_interface(x, y, N, width_factor, I1, I2, sigma_b, sigma_n, sampling=''):
    '''MC approximation to integral defining p(x,y).
    sampling: 'uniform', 'uniform_reparam' or 'p_tx'  '''

    if sampling=='uniform':
        I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
        I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )

        #draw N samples form Uniform dist
        tx_u = torch.distributions.Uniform(torch.ones(N)*I_min, torch.ones(N)*I_max).sample()
        tx_reshaped=tx_u.reshape(-1,1)

        #sum over all tx
        integral =   -math.log(N) + torch.logsumexp( log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)


    if sampling=='uniform_reparam':
        I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
        #I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )
        I_diff = (I2-I1)*math.erf(width_factor/np.sqrt(2))

        #draw N samples form Uniform dist
        k_u = torch.distributions.Uniform(torch.zeros(N), torch.ones(N)).sample()
        tx_reparam = k_u*I_diff + I_min
        tx_reshaped=tx_reparam.reshape(-1,1)

        #derivative of k_u wrt tx:
        dk_u = 1/I_diff

        #sum over all tx
        integral =  -torch.log(dk_u) -math.log(N) + torch.logsumexp( log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)


    if sampling=='p_tx' or sampling=='':
        txs=sample_from_p_tx(N, width_factor, I1, I2).reshape(-1, 1)

        #sum over all tx
        integral = -math.log(N)+ torch.logsumexp( log_p_y_cond_tx(y, txs, I1, I2, sigma_b, sigma_n) + log_p_x_cond_tx(x, txs, sigma_n), dim=0 )

    return  integral


def log_p_x_y_interior(x, y, tx, sigma_n):

    return math.log(2) + 2*torch.log(y) - math.log(math.gamma(3/2)) - 3*torch.log(sigma_n) - (y/sigma_n)**2 \
- torch.log(sigma_n) - 0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2


def log_p_x_y(x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm, sampling=''):
    '''FULL mixture log likelihood.
       log_p = [log_p1= log_p_x_y_interior I1, log_p2= log_p_x_y_interior I2, log_p3= log_p_x_y_interface]
       w = [w1, w2, w3] list
       log_w = w - logsumexp w '''


    log_p1 = log_p_x_y_interior(x, y, I1, sigma_n)
    log_p2 = log_p_x_y_interior(x, y, I2, sigma_n)
    log_p3 = log_p_x_y_interior(x, y, I3, sigma_n)
    log_p12 = log_p_x_y_interface(x, y, N, width_factor, I1, I2, sigma_b, sigma_n, sampling=sampling)
    log_p23 = log_p_x_y_interface(x, y, N, width_factor, I2, I3, sigma_b, sigma_n, sampling=sampling)
    log_p13 = log_p_x_y_interface(x, y, N, width_factor, I1, I3, sigma_b, sigma_n, sampling=sampling)

    log_p = torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1), log_p3.reshape(1,-1), log_p12.reshape(1,-1), log_p23.reshape(1,-1), log_p13.reshape(1,-1)), 0)


    #reshape to match log_p
    log_w_sm_squeezed=log_w_sm.unsqueeze(-1)#add dim
    log_w_sm_squeezed_reshaped = log_w_sm_squeezed.expand_as(log_p)

    return torch.logsumexp( log_w_sm_squeezed_reshaped + log_p, dim=0)


def L(x, y, N, width_factor, I1, I2, I3, sigma_b, sigma_n, log_w_sm, sampling=''):
    '''L = - sum_m log p (xm, ym)'''
    return - torch.sum ( log_p_x_y(x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm, sampling=sampling))


#
#
# # def log_p_tx(tx, I1, I2, sigma_b):
#
# #     out= torch.log(sigma_b) + 0.5*math.log(2*math.pi) - torch.log(I2-I1) \
# # +(torch.erfinv(  2*(tx-I1)/(I2-I1)  - 1) )**2
#
# #     return out
#
# def log_p_x_cond_tx(x, tx, sigma_n):
#     return -torch.log(sigma_n) -0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2
#
#
# def log_p_y_cond_tx(y, tx, I1, I2, sigma_b, sigma_n):
#
#     G_=G(tx, I1, I2, sigma_b)
#     exp_scaled_bessel_term = exp_scaled_modified_bessel(2*y*G_/(sigma_n**2), 0.5)
#
#     out = math.log(2) -2*torch.log(sigma_n) + (3/2)*torch.log(y) - 0.5*torch.log(G_) \
#     + torch.log(exp_scaled_bessel_term) + (2*y*G_/sigma_n**2)  -(y**2+G_**2)/sigma_n**2 #!!! log utanpå besselterm alone
#
#     return out
#
# #log_MC_uniform_int_p_x_y(x, y, N, width_factor, I1, I2, sigma_b, sigma_n)
#
# def log_p_x_y_interface(x, y, N, width_factor, I1, I2, sigma_b, sigma_n, sampling=''):
#     '''MC approximation to integral defining p(x,y).
#     sampling: 'uniform', 'uniform_reparam' or 'p_tx'  '''
#
#     if sampling=='uniform':
#         I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
#         I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )
#
#         #draw N samples form Uniform dist
#         tx_u = torch.distributions.Uniform(torch.ones(N)*I_min, torch.ones(N)*I_max).sample()
#         tx_reshaped=tx_u.reshape(-1,1)
#
#         #sum over all tx
#         integral =   -math.log(N) + torch.logsumexp( log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)
#
#
#     if sampling=='uniform_reparam':
#         I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
#         #I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )
#         I_diff = (I2-I1)*math.erf(width_factor/np.sqrt(2))
#
#         #draw N samples form Uniform dist
#         k_u = torch.distributions.Uniform(torch.zeros(N), torch.ones(N)).sample()
#         tx_reparam = k_u*I_diff + I_min
#         tx_reshaped=tx_reparam.reshape(-1,1)
#
#         #derivative of k_u wrt tx:
#         dk_u = 1/I_diff
#
#         #sum over all tx
#         integral =  -torch.log(dk_u) -math.log(N) + torch.logsumexp( log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)
#
#
#     if sampling=='p_tx' or sampling=='':
#         txs=sample_from_p_tx(N, width_factor, I1, I2).reshape(-1, 1)
#
#         #sum over all tx
#         integral = -math.log(N)+ torch.logsumexp( log_p_y_cond_tx(y, txs, I1, I2, sigma_b, sigma_n) + log_p_x_cond_tx(x, txs, sigma_n), dim=0 )
#
#     return  integral
#
#
# def log_p_x_y_interior(x, y, tx, sigma_n):
#
#     return math.log(2) + 2*torch.log(y) - math.log(math.gamma(3/2)) - 3*torch.log(sigma_n) - (y/sigma_n)**2 \
# - torch.log(sigma_n) - 0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2
#
#
# def log_p_x_y(x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm, sampling=''):
#     '''FULL mixture log likelihood.
#        log_p = [log_p1= log_p_x_y_interior I1, log_p2= log_p_x_y_interior I2, log_p3= log_p_x_y_interface]
#        w = [w1, w2, w3] list
#        log_w = w - logsumexp w '''
#
#
#     log_p1 = log_p_x_y_interior(x, y, I1, sigma_n)
#     log_p2 = log_p_x_y_interior(x, y, I2, sigma_n)
#     log_p3 = log_p_x_y_interior(x, y, I3, sigma_n)
#     log_p12 = log_p_x_y_interface(x, y, N, width_factor, I1, I2, sigma_b, sigma_n, sampling=sampling)
#     log_p23 = log_p_x_y_interface(x, y, N, width_factor, I2, I3, sigma_b, sigma_n, sampling=sampling)
#     log_p13 = log_p_x_y_interface(x, y, N, width_factor, I1, I3, sigma_b, sigma_n, sampling=sampling)
#
#     log_p = torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1), log_p3.reshape(1,-1), log_p12.reshape(1,-1), log_p23.reshape(1,-1), log_p13.reshape(1,-1)), 0)
#
#
#     #reshape to match log_p
#     log_w_sm_squeezed=log_w_sm.unsqueeze(-1)#add dim
#     log_w_sm_squeezed_reshaped = log_w_sm_squeezed.expand_as(log_p)
#
#     return torch.logsumexp( log_w_sm_squeezed_reshaped + log_p, dim=0)
#
#
# def L(x, y, N, width_factor, I1, I2, I3, sigma_b, sigma_n, log_w_sm, sampling=''):
#     '''L = - sum_m log p (xm, ym)'''
#     return - torch.sum ( log_p_x_y(x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm, sampling=sampling))
#



  ####### FOR PLOTTING
    ####### FOR PLOTTING
      ####### FOR PLOTTING

class ExpModifiedBesselFn(torch.autograd.Function):
    #USAGE: exp_scaled_modified_bessel = ExpModifiedBesselFn.apply
    @staticmethod
    def forward(ctx, inp, nu):
        ctx._nu = nu
        ctx.save_for_backward(inp)
        return torch.from_numpy(scipy.special.ive(nu, inp.detach().numpy()))
    @staticmethod
    def backward(ctx, grad_out):
        inp, = ctx.saved_tensors
        nu = ctx._nu
        # formula is from Wikipedia
        return 0.5* grad_out *(ExpModifiedBesselFn.apply(inp, nu - 1.0)+ExpModifiedBesselFn.apply(inp, nu + 1.0) - 2*ExpModifiedBesselFn.apply(inp, nu )), None






  ####### p(y)


def p_y_cond_tx_interior(y, sigma_n):
    '''p(y | tx) ~ chi distribution in phase interiors '''
    p_y_cond_tx_= 2*y**2/(math.gamma(3/2)*sigma_n**3) *torch.exp(-y**2/sigma_n**2)
    return p_y_cond_tx_


def p_y_cond_tx_interface(y,tx, I1, I2, sigma_b, sigma_n):
    '''p(y | tx) ~ non-central chi distribution in phase interiors '''

    exp_scaled_modified_bessel = ExpModifiedBesselFn.apply

    G_=G(tx, I1, I2, sigma_b)
    exp_scaled_bessel_term = exp_scaled_modified_bessel(2*y*G_/(sigma_n**2), 0.5)
    log_term =  torch.log(exp_scaled_bessel_term) + 2*y*G_/sigma_n**2  -(y**2+G_**2)/sigma_n**2
    p_y_cond_tx_=2/sigma_n**2 *torch.sqrt(y**3/G_) *torch.exp(log_term)
    return p_y_cond_tx_


def p_y_interface(y, N, width_factor, I1, I2, sigma_b, sigma_n):
    '''MC approximation of p(y)=integral p(y|tx) p(tx) dtx'''

    #!! Could include condition on sigma_n: doesn't work if sigma_n=0.

    tau=sample_from_p_tx(N, width_factor, I1, I2)

    p_y_cond_tx_ = p_y_cond_tx_interface(y,torch.reshape(tau,(-1,1)), I1, I2, sigma_b, sigma_n)#creates matrix of size MxN

    Integral_MC=torch.sum(p_y_cond_tx_, dim=0)/N #integral evaluated in y
    return Integral_MC



  ####### p(x)


def g(x, mu, sigma_n): #returns gauss with mean mu and std sigma_n
    return 1/(math.sqrt(2*math.pi)*sigma_n)*torch.exp(-((x-mu)/(sigma_n*math.sqrt(2)))**2)

def p_x_cond_tx(x, tx, sigma_n):
    return g(x, tx, sigma_n)

def p_x(x, N, width_factor, I1, I2, sigma_n): #remove sigma_b
    '''MC approximation of convolution integral, p(x) = d(x)*g(x)'''

    #!! Could include condition on sigma_n: doesn't work if sigma_n=0.

    tau=sample_from_p_tx(N, width_factor, I1, I2)
    gs=g(x, torch.reshape(tau,(-1,1)), sigma_n) #creates matrix of size MxN
    Integral_MC=torch.sum(gs, dim=0)/N #integral evaluated in x
    return Integral_MC

def I(z, I1, I2, sigma_b):
   return  I1+ (I2-I1)*0.5*(1+torch.erf(z/(sigma_b*math.sqrt(2))))


def I_np(z, I1, I2, sigma_b):
   return  I1+ (I2-I1)*0.5*(1+scipy.special.erf(z/(sigma_b*np.sqrt(2))))



def p_tx_np(tx, I1, I2, width_factor):
    return np.sqrt(2*np.pi)/(2*width_factor*(I2-I1))*np.exp(scipy.special.erfinv( 2*(tx-I1)/(I2-I1) -1 )**2)
