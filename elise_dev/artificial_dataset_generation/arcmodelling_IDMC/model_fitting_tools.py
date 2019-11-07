import torch
import numpy as np
import matplotlib.pyplot as plt

import matplotlib as mpl
from sklearn import mixture

import math
import scipy.special
import copy

from torch.utils.data import Dataset

from arcmodelling_IDMC import tools
from arcmodelling_IDMC import model_functions as mf


###########
##########


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

#
#
# def param_init(I_0, sigma_b_0, sigma_n_0, w_0):
#     '''Put parameters into list as tensors
#     Returns:Initial values of [I1, I2, I3, sigma_b, sigma_n, w1, w2, w3, w12, w23, w13]'''
#
#     param_0 = [torch.tensor(sigma_b_0), torch.tensor(sigma_n_0)] \
#     + [torch.tensor(I) for I in I_0] \
#     + [torch.tensor([w]) for w in w_0]
#
#     return param_0




class ArcModel3Phase(torch.nn.Module): #inherits from Module class
    '''Arc model for material with 3 phases'''

    def __init__(self, params_dict, width_factor, n_MC_components):
        super(ArcModel3Phase, self).__init__() #initializes superclass, does set-up

        self.params_dict=copy.deepcopy(params_dict) #need deepcopy to avoid two class instances changing the SAME parameters....
        #self.params_dict_0=copy.deepcopy(params_dict) #for later plotting

        self.n_MC_components=n_MC_components
        self.width_factor=width_factor


        self.sigma_b=torch.nn.Parameter(torch.tensor(self.params_dict['sigma_b']), requires_grad=True)
        self.sigma_n=torch.nn.Parameter(torch.tensor(self.params_dict['sigma_n']), requires_grad=True)

        self.I1=torch.nn.Parameter(torch.tensor(self.params_dict['I'][0]), requires_grad=True)
        self.I2=torch.nn.Parameter(torch.tensor(self.params_dict['I'][1]), requires_grad=True)
        self.I3=torch.nn.Parameter(torch.tensor(self.params_dict['I'][2]), requires_grad=True)


        self.w1=torch.nn.Parameter(torch.tensor([self.params_dict['w'][0]]), requires_grad=True)
        self.w2=torch.nn.Parameter(torch.tensor([self.params_dict['w'][1]]), requires_grad=True)
        self.w3=torch.nn.Parameter(torch.tensor([self.params_dict['w'][2]]), requires_grad=True)

        if len(params_dict['w'])<4: #interface components not spesified
            self.w12=torch.nn.Parameter(torch.tensor([0.1]), requires_grad=True)
            self.w23=torch.nn.Parameter(torch.tensor([0.1]), requires_grad=True)
            self.w13=torch.nn.Parameter(torch.tensor([0.1]), requires_grad=True)
            print('No interface weights provided - 0.1 added')
        else:
            self.w12=torch.nn.Parameter(torch.tensor([self.params_dict['w'][3]]), requires_grad=True)
            self.w23=torch.nn.Parameter(torch.tensor([self.params_dict['w'][4]]), requires_grad=True)
            self.w13=torch.nn.Parameter(torch.tensor([self.params_dict['w'][5]]), requires_grad=True)




    def log_p_tx(self, tx, width_factor, I1, I2):
        return -torch.log( 2*width_factor*(I2-I1)) + 0.5*math.log(2*math.pi) + ( torch.erfinv( 2*(tx-I1)/(I2-I1) -1 ) )**2


    def log_MC_uniform_int_p_x_y_reparam(self, x, y, N, width_factor, I1, I2, sigma_b, sigma_n):

        I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
        #I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )
        I_diff = (I2-I1)*math.erf(width_factor/np.sqrt(2))

        #draw N samples form Uniform dist
        k_u = torch.distributions.Uniform(torch.zeros(N), torch.ones(N)).sample()

        tx_reparam = k_u*I_diff + I_min

        tx_reshaped=tx_reparam.reshape(-1,1)

        #log(1/pu)=log(I_diff)

        integral =  torch.log(I_diff) -math.log(N) + torch.logsumexp( self.log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ self.log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + self.log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)
        #sum over all tx


        return integral


    def log_p_x_cond_tx(self, x, tx, sigma_n):
        return -torch.log(sigma_n) -0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2

    def G(self, x, I1, I2, sigma_b):
        arc=((I2-I1)/torch.sqrt(2*math.pi*sigma_b**2))*torch.exp(-( torch.erfinv( (  (2*x-2*I1)/(I2-I1) -1 ) )**2))
        #remove NaN outside I-range - put 0 (MUST PUT SOMETHING SLIGHTLY LARGER THAN = TO AVOIN NAN.......)
        #arc[torch.isnan(arc)] = torch.tensor(1E-10)#.double()
        return arc


    def log_p_y_cond_tx(self, y, tx, I1, I2, sigma_b, sigma_n):

        exp_scaled_modified_bessel = ExpModifiedBesselFn.apply

        G_=self.G(tx, I1, I2, sigma_b)
        exp_scaled_bessel_term = exp_scaled_modified_bessel(2*y*G_/(sigma_n**2), 0.5)

        out = math.log(2) -2*torch.log(sigma_n) + (3/2)*torch.log(y) - 0.5*torch.log(G_) \
        + torch.log(exp_scaled_bessel_term) + (2*y*G_/sigma_n**2)  -(y**2+G_**2)/sigma_n**2 #!!! log utanpå besselterm alone

        return out

    def log_p_x_y_interior(self, x, y, tx, sigma_n):
        return math.log(2) + 2*torch.log(y) - math.log(math.gamma(3/2)) - 3*torch.log(sigma_n) - (y/sigma_n)**2 \
        - torch.log(sigma_n) - 0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2



    def log_p_x_y(self, x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm):
        '''FULL mixture log likelihood.
           log_p = [log_p1= log_p_x_y_interior I1, log_p2= log_p_x_y_interior I2, log_p3= log_p_x_y_interface]
           w = [w1, w2, w3] list
           log_w = w - logsumexp w '''


        log_p1 = self.log_p_x_y_interior(x, y, I1, sigma_n)
        log_p2 = self.log_p_x_y_interior(x, y, I2, sigma_n)
        log_p3 = self.log_p_x_y_interior(x, y, I3, sigma_n)
        log_p12 = self.log_MC_uniform_int_p_x_y_reparam(x, y, N, width_factor, I1, I2, sigma_b, sigma_n)
        log_p23 = self.log_MC_uniform_int_p_x_y_reparam(x, y, N, width_factor, I2, I3, sigma_b, sigma_n)
        log_p13 = self.log_MC_uniform_int_p_x_y_reparam(x, y, N, width_factor, I1, I3, sigma_b, sigma_n)

        log_p = torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1), log_p3.reshape(1,-1), log_p12.reshape(1,-1), log_p23.reshape(1,-1), log_p13.reshape(1,-1)), 0)


        #reshape to match log_p
        log_w_sm_squeezed=log_w_sm.unsqueeze(-1)#add dim
        log_w_sm_squeezed_reshaped = log_w_sm_squeezed.expand_as(log_p)

        return torch.logsumexp( log_w_sm_squeezed_reshaped + log_p, dim=0)


    def L(self,x, y, N, width_factor, I1, I2, I3, sigma_b, sigma_n, log_w_sm):
        '''L = - sum_m log p (xm, ym)'''
        return - torch.sum ( self.log_p_x_y(x, y, N, width_factor, I1, I2,I3, sigma_b, sigma_n, log_w_sm) )


    def forward(self, x, y): # x, y must be tensor

        r=torch.cat([self.w1, self.w2, self.w3, self.w12, self.w23, self.w13], 0)
        log_w_sm = r - torch.logsumexp(r, dim=0)

        w1_split, w2_split, w3_split, w12_split, w23_split, w13_split =  torch.exp(log_w_sm).split(1)

        loss =self.L(x, y, self.n_MC_components, self.width_factor, self.I1, self.I2, self.I3, self.sigma_b, self.sigma_n, log_w_sm)

        return loss

    def evaluate_log_prob(self, x, y):

        log_p1 = self.log_p_x_y_interior(x, y, self.I1, self.sigma_n)
        log_p2 = self.log_p_x_y_interior(x, y, self.I2, self.sigma_n)
        log_p3 = self.log_p_x_y_interior(x, y, self.I3, self.sigma_n)
        log_p12 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n)
        log_p23 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I2, self.I3, self.sigma_b, self.sigma_n)
        log_p13 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I1, self.I3, self.sigma_b, self.sigma_n)

        #return torch.exp(torch.cat([log_p1, log_p2, log_p3, log_p12, log_p23, log_p13], 0))
        #return [log_p1, log_p2, log_p3, log_p12, log_p23, log_p13]
        return torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1), log_p3.reshape(1,-1), log_p12.reshape(1,-1), log_p23.reshape(1,-1), log_p13.reshape(1,-1)), 0)


    def evaluate_log_prob_3phases(self, x, y):

        log_p1 = self.log_p_x_y_interior(x, y, self.I1, self.sigma_n)
        log_p2 = self.log_p_x_y_interior(x, y, self.I2, self.sigma_n)
        log_p3 = self.log_p_x_y_interior(x, y, self.I3, self.sigma_n)
        log_p12 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n)
        log_p23 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I2, self.I3, self.sigma_b, self.sigma_n)
        log_p13 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I1, self.I3, self.sigma_b, self.sigma_n)

        #return torch.exp(torch.cat([log_p1, log_p2, log_p3, log_p12, log_p23, log_p13], 0))
        #return [log_p1, log_p2, log_p3, log_p12, log_p23, log_p13]
        return torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1), log_p3.reshape(1,-1), log_p12.reshape(1,-1), log_p23.reshape(1,-1), log_p13.reshape(1,-1)), 0)




    def get_softmaxed_weights(self):

        r=torch.cat([self.w1, self.w2, self.w3, self.w12, self.w23, self.w13], 0)
        log_w_sm = r - torch.logsumexp(r, dim=0)

        w1_split, w2_split, w3_split, w12_split, w23_split, w13_split =  torch.exp(log_w_sm).split(1)
        return w1_split, w2_split, w3_split, w12_split, w23_split, w13_split




    def print_params(self):
        for name, param in self.named_parameters():
            print(name, param.data.numpy())

        w1, w2, w3, w12, w23, w13 = self.get_softmaxed_weights()
        print('Weights, softmaxed: ', w1, w2, w3, w12, w23, w13 )




    #### PLOTTING ###

    def plot_with_x_hist(self, x_data, N_result=10000, nbins=500, plot_init=False,linewidth=2, individual_components=False, figsize=(16,8)):

        data_hist =np.histogram(x_data, bins=nbins)
        #create edges from tis data to be used with all data portions
        dbar=data_hist[1][1]-data_hist[1][0]
        xbar = data_hist[1][1:]-dbar/2
        xbar_tensor=torch.tensor(xbar).float()
        fig, ax=plt.subplots(1,1, figsize=figsize)
        ax.set_title('Intensity histogram with 1D model p(x)')
        data_hist_normed=data_hist[0]/(np.sum(data_hist[0]))
        ax.bar(xbar, data_hist_normed, dbar)


        w1, w2, w3, w12, w23, w13 = self.get_softmaxed_weights()


        ##RESULTS
        #interior
        p_x_I1=w1*mf.p_x_cond_tx(xbar_tensor, self.I1, self.sigma_n)
        p_x_I2=w2*mf.p_x_cond_tx(xbar_tensor, self.I2, self.sigma_n)
        p_x_I3=w3*mf.p_x_cond_tx(xbar_tensor, self.I3, self.sigma_n)
        #interface
        p_x_12=w12*mf.p_x(xbar_tensor, N_result, self.width_factor, self.I1, self.I2, self.sigma_n)
        p_x_23=w23*mf.p_x(xbar_tensor, N_result, self.width_factor, self.I2, self.I3, self.sigma_n)
        p_x_13=w13*mf.p_x(xbar_tensor, N_result, self.width_factor, self.I1, self.I3, self.sigma_n)


        norm_factor=np.sum(p_x_I1.detach().numpy())+np.sum(p_x_I2.detach().numpy())+np.sum(p_x_I3.detach().numpy()) \
      +np.sum(p_x_12.detach().numpy())+np.sum(p_x_23.detach().numpy())+np.sum(p_x_13.detach().numpy())


        total_model_np=(p_x_I1.detach().numpy()+p_x_I2.detach().numpy()+p_x_I3.detach().numpy() \
      +p_x_12.detach().numpy()+p_x_23.detach().numpy()+p_x_13.detach().numpy())/(norm_factor)

        if individual_components:
            ax.plot(xbar, p_x_I1.detach().numpy()/norm_factor, 'r', linewidth=linewidth, label='p_x_I1')
            ax.plot(xbar, p_x_I2.detach().numpy()/norm_factor, 'g', linewidth=linewidth, label='p_x_I2')
            ax.plot(xbar, p_x_I3.detach().numpy()/norm_factor, 'b', linewidth=linewidth, label='p_x_I3')
            ax.plot(xbar, p_x_12.detach().numpy()/norm_factor, 'y', linewidth=linewidth, label='p_x_12')
            ax.plot(xbar, p_x_13.detach().numpy()/norm_factor, 'c', linewidth=linewidth, label='p_x_13')
            ax.plot(xbar, p_x_23.detach().numpy()/norm_factor, 'k', linewidth=linewidth, label='p_x_23')



        ax.plot(xbar, total_model_np, 'm', linewidth=linewidth, label='Current Model')

        plt.legend()




    def plot_with_y_hist(self, y_data, N_result=10000, nbins=500, plot_init=False, individual_components=False, figsize=(16,8)):

        data_hist =np.histogram(y_data, bins=nbins)
        #create edges from tis data to be used with all data portions
        dbar=data_hist[1][1]-data_hist[1][0]
        xbar = data_hist[1][1:]-dbar/2
        xbar_tensor=torch.tensor(xbar).float()
        fig, ax=plt.subplots(1,1, figsize=figsize)
        ax.set_title('Gradient histogram with 1D model p(y)')
        data_hist_normed=data_hist[0]/np.sum(data_hist[0])
        ax.bar(xbar, data_hist_normed, dbar)

        w1, w2, w3, w12, w23, w13 = self.get_softmaxed_weights()

        ##RESULTS
        #interior
        p_x_I1=w1*mf.p_y_cond_tx_interior(xbar_tensor, self.sigma_n)
        p_x_I2=w2*mf.p_y_cond_tx_interior(xbar_tensor, self.sigma_n)
        p_x_I3=w3*mf.p_y_cond_tx_interior(xbar_tensor, self.sigma_n)
        #interface
        p_x_12=w12*mf.p_y_interface(xbar_tensor, N_result, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n)
        p_x_23=w23*mf.p_y_interface(xbar_tensor, N_result, self.width_factor, self.I2, self.I3, self.sigma_b, self.sigma_n)
        p_x_13=w13*mf.p_y_interface(xbar_tensor, N_result, self.width_factor, self.I1, self.I3, self.sigma_b, self.sigma_n)


        norm_factor=np.sum(p_x_I1.detach().numpy())+np.sum(p_x_I2.detach().numpy())+np.sum(p_x_I3.detach().numpy()) \
      +np.sum(p_x_12.detach().numpy())+np.sum(p_x_23.detach().numpy())+np.sum(p_x_13.detach().numpy())


        total_model_np=(p_x_I1.detach().numpy()+p_x_I2.detach().numpy()+p_x_I3.detach().numpy() \
      +p_x_12.detach().numpy()+p_x_23.detach().numpy()+p_x_13.detach().numpy())/norm_factor

        if individual_components:
            ax.plot(xbar, p_x_I1.detach().numpy()/norm_factor, 'r', linewidth=2, label='p_x_I1')
            ax.plot(xbar, p_x_I2.detach().numpy()/norm_factor, 'g', linewidth=2, label='p_x_I2')
            ax.plot(xbar, p_x_I3.detach().numpy()/norm_factor, 'b', linewidth=2, label='p_x_I3')
            ax.plot(xbar, p_x_12.detach().numpy()/norm_factor, 'y', linewidth=2, label='p_x_12')
            ax.plot(xbar, p_x_13.detach().numpy()/norm_factor, 'c', linewidth=2, label='p_x_13')
            ax.plot(xbar, p_x_23.detach().numpy()/norm_factor, 'k', linewidth=2, label='p_x_23')


        ax.plot(xbar, total_model_np, 'm', linewidth=2, label='Current Model')

        plt.legend()


    def plot_2D_gridplot(self, Ivals, Gvals, N_result=10000, figsize=(10,10), cmap='viridis',cmap_gamma=0.2, title='Model evaluated on grid', axis='on'):
        '''will plot the model on a nbins*nbins grid
        Ivals, Gvals should be linspace arrays determining the grid'''


        xxx=Ivals
        yyy=Gvals
        X,Y=np.meshgrid(xxx,yyy)

        x_grid=torch.tensor(X.ravel()).float()
        y_grid=torch.tensor(Y.ravel()).float()

        #evaluate model in grid values, then respame to grid dimensions
        w1, w2, w3, w12, w23, w13 = self.get_softmaxed_weights()
        weights=torch.cat([w1, w2, w3, w12, w23, w13], 0)

        log_model_2D = self.log_p_x_y(x_grid, y_grid, N_result, self.width_factor, self.I1, self.I2,self.I3, self.sigma_b, self.sigma_n, weights)

        model_2D=torch.exp(log_model_2D)

        model_2D_image= np.reshape(model_2D.detach().numpy(), (len(Ivals), len(Gvals))).T

        #np.save('hist_arc.npy', model_2D_image)

        #normalize
        bin_area = (xxx[1]-xxx[0])*(yyy[1]-yyy[0])
        model_2D_image/=(np.sum(model_2D_image))*bin_area

        fig,ax = plt.subplots(1,1, figsize=figsize)
        ax.axis(axis)
        im=ax.pcolormesh(X,Y, model_2D_image.T, cmap=cmap, norm=mpl.colors.PowerNorm(gamma=cmap_gamma))
        ax.set_title(title)

        fig.colorbar(im, ax=ax)#, extend='max')

        #plt.show()
        return model_2D_image.T









class paramTracker():

    def __init__(self):
        self.param_lists = []

    def track(self, current_param_iterator):
        list_current = np.array([param.data.numpy() for param in current_param_iterator])
        if len(list_current)==11:
            weights = list_current[5:]
            w_softmaxed = np.exp(weights)
            w_softmaxed /= np.sum(w_softmaxed)
            list_current[5:]=w_softmaxed
        if len(list_current)==7:
            weights = list_current[4:]
            w_softmaxed = np.exp(weights)
            w_softmaxed /= np.sum(w_softmaxed)
            list_current[4:]=w_softmaxed
        self.param_lists.append(list_current)


    def plot_params_tracked(self, loss_list):

        params_array=np.array(self.param_lists)
        no_params = int(np.shape(self.param_lists)[1])
        no_rows = int(np.ceil(no_params/3))

        if no_params==11:
            param_names=['sigma_b', 'sigma_n', 'I1', 'I2', 'I3', 'w1', 'w2', 'w3', 'w12', 'w23', 'w13']

        elif no_params==7:
            param_names=['sigma_b', 'sigma_n', 'I1', 'I2',  'w1', 'w2', 'w12']
        else:
            param_names=['' for i in range(no_params)]

        fig = plt.figure(figsize=(16, 4*no_rows))
        #plot loss
        ax = fig.add_subplot(no_rows, 3, 1)
        ax.plot(loss_list, 'r-*')
        ax.set_title('Loss. Final value: '+str(loss_list[-1]))
        #plot params
        for i in range(no_params):
            ax = fig.add_subplot(no_rows, 3, i+2)
            ax.plot(params_array[:,i], 'b-*')
            ax.set_title(param_names[i]+', Final value: '+str(params_array[:,i][-1]))



# test=0
# if test:
#     params_tracked = paramTracker()
#     params_tracked.track(GMM3model.parameters())
#     params_tracked.track(GMM3model.parameters())
#     params_tracked.track(GMM3model.parameters())
#
#     params_tracked.plot_params_tracked([0])

##############
## Prep
#############


def get_intensity_and_gradient_arrays(data_filename, mask=[]):

    data = np.load(data_filename)
    data_gradient = tools.gradient3D(data)

    if len(mask)>0: #needs more RAM...

        mask=mask[1:-1, 1:-1, 1:-1]
        data=data[1:-1, 1:-1, 1:-1]
        data_gradient=data_gradient[1:-1, 1:-1, 1:-1]
        x_data = torch.tensor(data[mask].ravel()).float()
        y_data =  torch.tensor(data_gradient[mask].ravel()).float()

    else:
        x_data = torch.tensor(data[1:-1, 1:-1, 1:-1].ravel()).float()
        y_data =  torch.tensor(data_gradient[1:-1, 1:-1, 1:-1].ravel()).float()

    return x_data, y_data


class RealDataSet(Dataset):
    '''Creates dataset so that dataloader functionality can be applied
    From filename OR data.
    data_filename: path and filename to .npy dataset
    self.x: intensity tensor
    self.y: gradient tensor'''

    def __init__(self, data_filename='', x_data=[], y_data=[]):

        if len(data_filename)>0:
            self.x, self.y = get_intensity_and_gradient_arrays(data_filename)
        elif type(x_data)==np.ndarray:
            self.x = torch.tensor(x_data).float()
            self.y = torch.tensor(y_data).float()
        else:
            self.x = x_data
            self.y = y_data

        self.minx = torch.min(self.x)
        self.maxx = torch.max(self.x)
        self.miny = torch.min(self.y)
        self.maxy = torch.max(self.y)

        #for segmentation
        self.labels=torch.zeros(len(self.x))


    def __getitem__(self, index):
        return self.x[index], self.y[index]

    def __len__(self):
        return len(self.x)

    def sample(self, sample_size=1):
        inds = np.random.randint(0, len(self.x), sample_size)
        return self.x[inds], self.y[inds]








def perform_GMM_np(data_np, n_components, plot=False, n_init=1, nbins=500):

    #reshape data
    n_samples=len(data_np)
    X_train = np.concatenate([data_np.reshape((n_samples, 1)), np.zeros((n_samples, 1))], axis=1)

    # fit a Gaussian Mixture Model
    clf = mixture.GaussianMixture(n_components=n_components, covariance_type='full', n_init=n_init)
    clf.fit(X_train)
    if clf.converged_!=True:
        print(' !! Did not converge! Converged: ',clf.converged_)

    labels=clf.predict(X_train)

    means=[]
    stds=[]
    weights=[]
    for c in range(n_components):
        component=X_train[labels==c][:,0]
        means.append(np.mean(component))
        stds.append(np.std(component))
        weights.append(len(component)/len(data_np))

    if plot:
        gaussian = lambda x, mu, s, A: A*np.exp(-0.5*(x-mu)**2/s**2)/np.sqrt(2*np.pi*s**2)
        fig, ax=plt.subplots(1, figsize=(10, 6))

        hist, bin_edges = np.histogram(data_np, bins=nbins)
        bin_size=np.diff(bin_edges)
        bin_centers = bin_edges[:-1] +  bin_size/ 2
        hist_normed = hist/(n_samples*bin_size) #normalizing to get 1 under graph
        ax.bar(bin_centers,hist_normed, bin_size, alpha=0.5)
        ax.set_title('Histogram, '+str(n_samples)+' datapoints')

        #COLORMAP WITH EVENLY SPACED COLORS!
        colors=plt.cm.rainbow(np.linspace(0,1,n_components))#rainbow, plasma, autumn, viridis...

        x_vals=np.linspace(np.min(bin_edges), np.max(bin_edges), 500)

        for c in range(n_components):
            ax.plot(x_vals, gaussian(x_vals, means[c], stds[c], weights[c]), color=colors[c], linewidth=2, label='mean=%.2f'%(means[c]))
            ax.arrow(means[c], weights[c], 0, 0.1)
        plt.legend()

    return means, stds, weights


def plot_GMM(data_np, means, stds, weights, nbins=100, title='', figsize=(10,6)):

    gaussian = lambda x, mu, s, A: A*np.exp(-0.5*(x-mu)**2/s**2)/np.sqrt(2*np.pi*s**2)
    fig, ax=plt.subplots(1, figsize=figsize)

    n_samples=len(data_np)
    n_components=len(means)
    hist, bin_edges = np.histogram(data_np, bins=nbins)
    bin_size=np.diff(bin_edges)
    bin_centers = bin_edges[:-1] +  bin_size/ 2
    hist_normed = hist/(n_samples*bin_size) #normalizing to get 1 under graph
    ax.bar(bin_centers,hist_normed, bin_size, alpha=0.5)
    ax.set_title(title)

    #COLORMAP WITH EVENLY SPACED COLORS!
    colors=plt.cm.rainbow(np.linspace(0,1,n_components))#rainbow, plasma, autumn, viridis...

    x_vals=np.linspace(np.min(bin_edges), np.max(bin_edges), 500)

    for c in range(n_components):
        ax.plot(x_vals, gaussian(x_vals, means[c], stds[c], weights[c]), color=colors[c], linewidth=2, label='mean=%.2f'%(means[c]))
        ax.arrow(means[c], weights[c], 0, 0.1)
    plt.legend()


#
# def param_init(I_0, sigma_b_0, sigma_n_0, w_0):
#
#     param_0 = [torch.tensor(I, requires_grad=True) for I in I_0]+\
#     [torch.tensor(sigma_b_0, requires_grad=True), torch.tensor(sigma_n_0, requires_grad=True)]+\
#     [torch.tensor(w, requires_grad=True) for w in w_0]
#
#     return param_0


class ArcModel2Phase(torch.nn.Module): #inherits from Module class
    '''Arc model for material with 2 phases'''

    def __init__(self, params_dict, width_factor, n_MC_components):
        super(ArcModel2Phase, self).__init__() #initializes superclass, does set-up

        self.params_dict=copy.deepcopy(params_dict) #need deepcopy to avoid two class instances changing the SAME parameters....
        #self.params_dict_0=copy.deepcopy(params_dict) #for later plotting

        self.n_MC_components=n_MC_components
        self.width_factor=width_factor


        self.sigma_b=torch.nn.Parameter(torch.tensor(self.params_dict['sigma_b']), requires_grad=True)
        self.sigma_n=torch.nn.Parameter(torch.tensor(self.params_dict['sigma_n']), requires_grad=True)

        self.I1=torch.nn.Parameter(torch.tensor(self.params_dict['I'][0]), requires_grad=True)
        self.I2=torch.nn.Parameter(torch.tensor(self.params_dict['I'][1]), requires_grad=True)


        self.w1=torch.nn.Parameter(torch.tensor([self.params_dict['w'][0]]), requires_grad=True)
        self.w2=torch.nn.Parameter(torch.tensor([self.params_dict['w'][1]]), requires_grad=True)

        if len(params_dict['w'])<3: #interface components not spesified
            self.w12=torch.nn.Parameter(torch.tensor([0.1]), requires_grad=True)
            print('No interface weights provided - 0.1 added')
        else:
            self.w12=torch.nn.Parameter(torch.tensor([self.params_dict['w'][2]]), requires_grad=True)




    def log_p_tx(self, tx, width_factor, I1, I2):
        return -torch.log( 2*width_factor*(I2-I1)) + 0.5*math.log(2*math.pi) + ( torch.erfinv( 2*(tx-I1)/(I2-I1) -1 ) )**2


    def log_MC_uniform_int_p_x_y_reparam(self, x, y, N, width_factor, I1, I2, sigma_b, sigma_n):

        I_min = I1 +  0.5*(I2-I1)*(1 + math.erf(-width_factor/np.sqrt(2)) )
        #I_max = I1 +  0.5*(I2-I1)*(1 + math.erf(width_factor/np.sqrt(2)) )
        I_diff = (I2-I1)*math.erf(width_factor/np.sqrt(2))

        #draw N samples form Uniform dist
        k_u = torch.distributions.Uniform(torch.zeros(N), torch.ones(N)).sample()

        tx_reparam = k_u*I_diff + I_min

        tx_reshaped=tx_reparam.reshape(-1,1)

        #log(1/pu)=log(I_diff)

        integral =  torch.log(I_diff) -math.log(N) + torch.logsumexp( self.log_p_x_cond_tx(x, tx_reshaped, sigma_n)+ self.log_p_y_cond_tx(y, tx_reshaped, I1, I2, sigma_b, sigma_n) + self.log_p_tx(tx_reshaped,width_factor, I1, I2), dim=0)
        #sum over all tx


        return integral


    def log_p_x_cond_tx(self, x, tx, sigma_n):
        return -torch.log(sigma_n) -0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2

    def G(self, x, I1, I2, sigma_b):
        arc=((I2-I1)/torch.sqrt(2*math.pi*sigma_b**2))*torch.exp(-( torch.erfinv( (  (2*x-2*I1)/(I2-I1) -1 ) )**2))
        #remove NaN outside I-range - put 0 (MUST PUT SOMETHING SLIGHTLY LARGER THAN = TO AVOIN NAN.......)
        #arc[torch.isnan(arc)] = torch.tensor(1E-10)#.double()
        return arc


    def log_p_y_cond_tx(self, y, tx, I1, I2, sigma_b, sigma_n):

        exp_scaled_modified_bessel = ExpModifiedBesselFn.apply

        G_=self.G(tx, I1, I2, sigma_b)
        exp_scaled_bessel_term = exp_scaled_modified_bessel(2*y*G_/(sigma_n**2), 0.5)

        out = math.log(2) -2*torch.log(sigma_n) + (3/2)*torch.log(y) - 0.5*torch.log(G_) \
        + torch.log(exp_scaled_bessel_term) + (2*y*G_/sigma_n**2)  -(y**2+G_**2)/sigma_n**2 #!!! log utanpå besselterm alone

        return out

    def log_p_x_y_interior(self, x, y, tx, sigma_n):
        return math.log(2) + 2*torch.log(y) - math.log(math.gamma(3/2)) - 3*torch.log(sigma_n) - (y/sigma_n)**2 \
        - torch.log(sigma_n) - 0.5*math.log(2*math.pi) -0.5*((x-tx)/sigma_n)**2



    def log_p_x_y(self, x, y, N, width_factor, I1, I2,sigma_b, sigma_n, log_w_sm):
        '''FULL mixture log likelihood.
           log_p = [log_p1= log_p_x_y_interior I1, log_p2= log_p_x_y_interior I2, log_p3= log_p_x_y_interface]
           w = [w1, w2, w3] list
           log_w = w - logsumexp w '''


        log_p1 = self.log_p_x_y_interior(x, y, I1, sigma_n)
        log_p2 = self.log_p_x_y_interior(x, y, I2, sigma_n)
        log_p12 = self.log_MC_uniform_int_p_x_y_reparam(x, y, N, width_factor, I1, I2, sigma_b, sigma_n)

        log_p = torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1),  log_p12.reshape(1,-1)), 0)


        #reshape to match log_p
        log_w_sm_squeezed=log_w_sm.unsqueeze(-1)#add dim
        log_w_sm_squeezed_reshaped = log_w_sm_squeezed.expand_as(log_p)

        return torch.logsumexp( log_w_sm_squeezed_reshaped + log_p, dim=0)


    def L(self,x, y, N, width_factor, I1, I2,  sigma_b, sigma_n, log_w_sm):
        '''L = - sum_m log p (xm, ym)'''
        return - torch.sum ( self.log_p_x_y(x, y, N, width_factor, I1, I2, sigma_b, sigma_n, log_w_sm) )


    def forward(self, x, y): # x, y must be tensor

        r=torch.cat([self.w1, self.w2, self.w12], 0)
        log_w_sm = r - torch.logsumexp(r, dim=0)

        #w1_split, w2_split,  w12_split =  torch.exp(log_w_sm).split(1)

        loss =self.L(x, y, self.n_MC_components, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n, log_w_sm)

        return loss

    def evaluate_log_prob(self, x, y):

        log_p1 = self.log_p_x_y_interior(x, y, self.I1, self.sigma_n)
        log_p2 = self.log_p_x_y_interior(x, y, self.I2, self.sigma_n)
        log_p12 = self.log_MC_uniform_int_p_x_y_reparam(x, y, self.n_MC_components, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n)

        return torch.cat((log_p1.reshape(1,-1), log_p2.reshape(1,-1),  log_p12.reshape(1,-1)), 0)


    def get_softmaxed_weights(self):

        r=torch.cat([self.w1, self.w2, self.w12], 0)
        log_w_sm = r - torch.logsumexp(r, dim=0)
        w1_split, w2_split,  w12_split =  torch.exp(log_w_sm).split(1)
        return w1_split, w2_split,  w12_split



    def print_params(self):

        for name, param in self.named_parameters():
            print(name, param.data.numpy())

        w1, w2, w12 = self.get_softmaxed_weights()
        print('Weights, softmaxed: ', w1, w2, w12)




    #### PLOTTING ###

    def plot_with_x_hist(self, x_data, N_result=10000, nbins=500, linewidth=2, individual_components=False, figsize=(16,8)):

        data_hist =np.histogram(x_data, bins=nbins)
        #create edges from tis data to be used with all data portions
        dbar=data_hist[1][1]-data_hist[1][0]
        xbar = data_hist[1][1:]-dbar/2
        xbar_tensor=torch.tensor(xbar).float()
        fig, ax=plt.subplots(1,1, figsize=figsize)
        ax.set_title('Intensity histogram with 1D model p(x)')
        data_hist_normed=data_hist[0]/(np.sum(data_hist[0]))
        ax.bar(xbar, data_hist_normed, dbar)


        ##RESULTS
        #interior
        w1, w2, w12 = self.get_softmaxed_weights()
        p_x_I1=w1*mf.p_x_cond_tx(xbar_tensor, self.I1, self.sigma_n)
        p_x_I2=w2*mf.p_x_cond_tx(xbar_tensor, self.I2, self.sigma_n)
        #interface
        p_x_12=w12*mf.p_x(xbar_tensor, N_result, self.width_factor, self.I1, self.I2, self.sigma_n)


        norm_factor=np.sum(p_x_I1.detach().numpy())+np.sum(p_x_I2.detach().numpy()) +np.sum(p_x_12.detach().numpy())


        total_model_np=(p_x_I1.detach().numpy()+p_x_I2.detach().numpy()  +p_x_12.detach().numpy())/(norm_factor)

        if individual_components:
            ax.plot(xbar, p_x_I1.detach().numpy()/norm_factor, 'r', linewidth=linewidth, label='p_x_I1')
            ax.plot(xbar, p_x_I2.detach().numpy()/norm_factor, 'g', linewidth=linewidth, label='p_x_I2')
            ax.plot(xbar, p_x_12.detach().numpy()/norm_factor, 'y', linewidth=linewidth, label='p_x_12')

        ax.plot(xbar, total_model_np, 'm', linewidth=linewidth, label='Current Model')

        plt.legend()




    def plot_with_y_hist(self, y_data, N_result=10000, nbins=500, plot_init=False, individual_components=False, figsize=(16,8)):

        data_hist =np.histogram(y_data, bins=nbins)
        #create edges from tis data to be used with all data portions
        dbar=data_hist[1][1]-data_hist[1][0]
        xbar = data_hist[1][1:]-dbar/2
        xbar_tensor=torch.tensor(xbar).float()
        fig, ax=plt.subplots(1,1, figsize=figsize)
        ax.set_title('Gradient histogram with 1D model p(y)')
        data_hist_normed=data_hist[0]/np.sum(data_hist[0])
        ax.bar(xbar, data_hist_normed, dbar)

        w1, w2, w12 = self.get_softmaxed_weights()

        ##RESULTS
        #interior
        p_x_I1=w1*mf.p_y_cond_tx_interior(xbar_tensor, self.sigma_n)
        p_x_I2=w2*mf.p_y_cond_tx_interior(xbar_tensor, self.sigma_n)
        #interface
        p_x_12=w12*mf.p_y_interface(xbar_tensor, N_result, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n)


        norm_factor=np.sum(p_x_I1.detach().numpy())+np.sum(p_x_I2.detach().numpy()) +np.sum(p_x_12.detach().numpy())


        total_model_np=(p_x_I1.detach().numpy()+p_x_I2.detach().numpy() +p_x_12.detach().numpy())/norm_factor

        if individual_components:
            ax.plot(xbar, p_x_I1.detach().numpy()/norm_factor, 'r', linewidth=2, label='p_x_I1')
            ax.plot(xbar, p_x_I2.detach().numpy()/norm_factor, 'g', linewidth=2, label='p_x_I2')
            ax.plot(xbar, p_x_12.detach().numpy()/norm_factor, 'y', linewidth=2, label='p_x_12')


        ax.plot(xbar, total_model_np, 'm', linewidth=2, label='Current Model')

        plt.legend()


    def plot_2D_gridplot(self, Ivals, Gvals, N_result=10000, figsize=(10,10), cmap='viridis',cmap_gamma=0.2, title='Model evaluated on grid', axis='on'):
        '''will plot the model on a nbins*nbins grid
        Ivals, Gvals should be linspace arrays determining the grid'''


        xxx=Ivals
        yyy=Gvals
        X,Y=np.meshgrid(xxx,yyy)

        x_grid=torch.tensor(X.ravel()).float()
        y_grid=torch.tensor(Y.ravel()).float()

        #evaluate model in grid values, then respame to grid dimensions
        w1, w2, w12 = self.get_softmaxed_weights()
        weights=torch.cat([w1, w2,w12], 0)

        log_model_2D = self.log_p_x_y(x_grid, y_grid, N_result, self.width_factor, self.I1, self.I2, self.sigma_b, self.sigma_n, weights)

        model_2D=torch.exp(log_model_2D)

        model_2D_image= np.reshape(model_2D.detach().numpy(), (len(Ivals), len(Gvals))).T

        #np.save('hist_arc.npy', model_2D_image)

        #normalize
        bin_area = (xxx[1]-xxx[0])*(yyy[1]-yyy[0])
        model_2D_image/=(np.sum(model_2D_image))*bin_area

        fig,ax = plt.subplots(1,1, figsize=figsize)
        ax.axis(axis)
        im=ax.pcolormesh(X,Y, model_2D_image.T, cmap=cmap, norm=mpl.colors.PowerNorm(gamma=cmap_gamma))
        ax.set_title(title)

        fig.colorbar(im, ax=ax)#, extend='max')

        #plt.show()
        return model_2D_image.T
