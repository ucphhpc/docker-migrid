
import numpy as np
import time
import matplotlib.pyplot as plt
import matplotlib as mpl
from skimage.morphology import convex_hull_image
import scipy.ndimage as snd

#import tifffile
import os
import skimage



##############
## DIV DATA PLOT
##############

def scale(arr, amin=0, amax=1):
    arr01=(arr-np.min(arr))/(np.max(arr)-np.min(arr))
    return arr01*(amax-amin)+amin


def plot_2D_image(image_array, title='', cmap='Greys_r', axis='equal', fig_external=[], figsize=(5,5), colorbar=False, vmin=None, vmax=None, cmap_gamma=1.):
    '''send in fig_external=[fig,ax] if figure should be plotted in subplot'''

    if len(fig_external)==0:
        fig,ax = plt.subplots(1, figsize=figsize)
    else:
        fig = fig_external[0]
        ax = fig_external[1]

    xxx=np.arange(0, np.shape(image_array)[1])
    yyy=np.arange(0, np.shape(image_array)[0])
    X,Y=np.meshgrid(xxx,yyy)

    ax.axis(axis)
    im=ax.pcolormesh(Y,X, image_array, cmap=cmap, vmin=vmin, vmax=vmax, norm=mpl.colors.PowerNorm(gamma=cmap_gamma))
    ax.set_title(title)
    if colorbar:
        fig.colorbar(im, ax=ax)

    if len(fig_external)==0:
        plt.show() #when external figure, show must not be called



def plot_center_slices(volume, title='', save_filename='', cmap='viridis', colorbar=False, vmin=None, vmax=None):
        shape=np.shape(volume)
        fig, ax=plt.subplots(1,3, figsize=(15,5))
        fig.suptitle(title)
        im=ax[0].imshow(volume[:,:, int(shape[2]/2)], cmap=cmap, vmin=vmin, vmax=vmax)
        ax[0].set_title('Center z slice')
        ax[1].imshow(volume[:,int(shape[1]/2),:], cmap=cmap, vmin=vmin, vmax=vmax)
        ax[1].set_title('Center y slice')
        ax[2].imshow(volume[int(shape[0]/2),:,:], cmap=cmap, vmin=vmin, vmax=vmax)
        ax[2].set_title('Center x slice')

        if colorbar:
            fig.subplots_adjust(right=0.8)
            cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
            fig.colorbar(im, cax=cbar_ax)


        if len(save_filename)>0:
            plt.savefig(save_filename)

        plt.show()



def plot_hist(data, nbins=100, fig_external=[], title='', alpha=1, figsize=(10,6)):
    if len(fig_external)==0:
        fig,ax = plt.subplots(1, 1, figsize=figsize)
    else:
        fig = fig_external[0]
        ax = fig_external[1]

    ax.set_title(title)
    ax.hist(data, bins=nbins, alpha=alpha)

def plot_2D_histogram(intensity_toPlot, gradient_toPlot, nbins=1000,  norm_hist=False, bin_arrays=[], title='', save_filename='', fig_external=[], set_colorbar=True, figsize=(8,8), cmap_gamma=0.2, cmap='viridis'):
    '''n_bin is int or [array, array] '''

    if len(bin_arrays)==2:

        hist_bins=bin_arrays
    else:
        hist_bins=nbins


    hist=np.histogram2d(intensity_toPlot, gradient_toPlot, bins=hist_bins)
    zzz=hist[0]


    xxx=np.linspace(np.min(intensity_toPlot), np.max(intensity_toPlot), np.shape(zzz)[0])
    yyy=np.linspace(np.min(gradient_toPlot), np.max(gradient_toPlot), np.shape(zzz)[1]) #To scale axis
    X,Y=np.meshgrid(xxx,yyy)


    if norm_hist:
        bin_area = (hist[1][1]-hist[1][0])*(hist[2][1]-hist[2][0])
        #bin_area = (xxx[1]-xxx[0])*(yyy[1]-yyy[0])
        zzz/=(np.sum(zzz))*bin_area



    if len(fig_external)==0:
        fig,ax = plt.subplots(1, figsize=figsize)
    else:
        fig = fig_external[0]
        ax = fig_external[1]
    #ax.set_facecolor((0.2, 0.2, 0.8))

    im=ax.pcolormesh(X,Y, zzz.T, cmap=cmap, norm=mpl.colors.PowerNorm(gamma=cmap_gamma))

    ax.set_title(title)
    if set_colorbar:
        fig.colorbar(im)

    #
    # if len(fig_external)==0:
    #     plt.show() #when external figure, show must not be called


    if len(save_filename)>0:
        plt.show()
        plt.savefig(save_filename)

    return zzz

    #cmap.set_bad(‘grey’) #chose color of NA
    # norm=LogNorm(intensity_toPlot.min(), intensity_toPlot.max())  #using from matplotlib.colors import LogNorm


##############
## DIV DATA CALC
##############


def gradient3D(vol):
    ''' computes 3D gradient'''
    gradx, grady, gradz = np.gradient(vol)#/np.max(np.gradient(volume))
    gradient_3D = np.sqrt(gradx**2 + grady**2+ gradz**2)
    return gradient_3D

def gradient2D(image):
    ''' computes 3D gradient'''
    gradx, grady = np.gradient(image)#/np.max(np.gradient(volume))
    gradient_2D = np.sqrt(gradx**2 + grady**2)
    return gradient_2D


def masks_edge_interior(volume):
    xlen, ylen, zlen = np.shape(volume)
    edges = np.zeros((xlen, ylen, zlen))
    edges[0,:,:]=1
    edges[xlen-1,:,:]=1
    edges[:,0,:]=1
    edges[:,ylen-1,:]=1
    edges[:,:,0]=1
    edges[:,:,zlen-1]=1

    edge_mask= (edges==1)
    interior_mask = (edges==0)

    return edge_mask, interior_mask


def gaussian_filter(volume, sigma, mode='reflect'):

    return snd.gaussian_filter(volume, sigma, mode=mode)


def convex_hull_3d(volume):
    '''Finds convex hull of volume, SLICE BY SLICE (can give sritfacts.. OK for simple masks)'''
    mask=[]
    for slice_no in range(np.shape(volume)[2]):
        data_slice = volume[:,:,slice_no]
        mask.append(convex_hull_image(data_slice).T)

    return np.array(mask).T #orient so that z dir (slices) is last coordinate


################
## TIFF and TIF
###############

#
# def save_3D_tiff(filename, array):
#
#     #array has dim x,y,z while tifffile saves as z,y,x - flip array to avoid this
#
#     #tifffile.imwrite(filename, np.transpose(array), photometric='minisblack')
#     tifffile.imsave(filename, np.transpose(array).astype(np.float32), photometric='minisblack')
#     print('Array saved as 3D greyscale tiff: ', filename)
#
#
#
#
# def load_3D_tiff(filename):
#
#     data = tifffile.imread(filename)
#     print('3D tiff loaded: ', filename)
#     return np.transpose(data)




def load_all_tif_slices(directory):
    '''Loads all tif slices in file directory into nympy array'''

    data = []

    for ind, filename in enumerate(sorted(os.listdir(directory))):
        if filename.endswith(".tif"):
            image = skimage.io.imread(directory+filename)
            data.append(image)

    return np.array(data).T










##########
## DIV
#########


def extract_sample(data_int, data_grad=[], sample_size=10):
    '''Draw sample_size samples form Uniform dist'''

    inds = np.random.randint(0, len(data_int), sample_size)

    if len(data_grad)>0:
        return data_int[inds], data_grad[inds]
    else:
        return data_int[inds]




import time
class tinytimer():
# USE:
#timer=tinytimer()
##code to be timed
#timer.stop()

    def __init__(self, namestring='timer'):
        self.start=time.time()
        self.name=namestring

    def stop(self):
        self.total=(time.time()-self.start)
        print('Total time, %s: \t %.2f sec \n \t \t %.2f min'%(self.name, self.total, (self.total/60)))



class DraggableColorbar(object):
    '''Example usage:
import scipy.ndimage as snd
import numpy as np

# Create random image
nx, ny = 256, 256
image = np.random.randn(ny, nx)
image += np.random.normal(3., 0.01, image.shape)
image = snd.gaussian_filter(image, 1)

%matplotlib notebook
img = plt.imshow(image,cmap='viridis')
cbar = plt.colorbar(format='%05.2f')
#cbar.set_norm(mynormalize.MyNormalize(vmin=image.min(),vmax=image.max(),stretch='linear'))
cbar = DraggableColorbar(cbar,img)
cbar.connect()
plt.show()
'''




    def __init__(self, cbar, mappable):
        self.cbar = cbar
        self.mappable = mappable
        self.press = None
        self.cycle = sorted([i for i in dir(plt.cm) if hasattr(getattr(plt.cm,i),'N')])
        self.index = self.cycle.index(cbar.get_cmap().name)

    def connect(self):
        """connect to all the events we need"""
        self.cidpress = self.cbar.patch.figure.canvas.mpl_connect(
            'button_press_event', self.on_press)
        self.cidrelease = self.cbar.patch.figure.canvas.mpl_connect(
            'button_release_event', self.on_release)
        self.cidmotion = self.cbar.patch.figure.canvas.mpl_connect(
            'motion_notify_event', self.on_motion)
        self.keypress = self.cbar.patch.figure.canvas.mpl_connect(
            'key_press_event', self.key_press)

    def on_press(self, event):
        """on button press we will see if the mouse is over us and store some data"""
        if event.inaxes != self.cbar.ax: return
        self.press = event.x, event.y

    def key_press(self, event):
        if event.key=='down':
            self.index += 1
        elif event.key=='up':
            self.index -= 1
        if self.index<0:
            self.index = len(self.cycle)
        elif self.index>=len(self.cycle):
            self.index = 0
        cmap = self.cycle[self.index]
        self.cbar.set_cmap(cmap)
        self.cbar.draw_all()
        self.mappable.set_cmap(cmap)
        self.mappable.get_axes().set_title(cmap)
        self.cbar.patch.figure.canvas.draw()

    def on_motion(self, event):
        'on motion we will move the rect if the mouse is over us'
        if self.press is None: return
        if event.inaxes != self.cbar.ax: return
        xprev, yprev = self.press
        dx = event.x - xprev
        dy = event.y - yprev
        self.press = event.x,event.y
        #print 'x0=%f, xpress=%f, event.xdata=%f, dx=%f, x0+dx=%f'%(x0, xpress, event.xdata, dx, x0+dx)
        scale = self.cbar.norm.vmax - self.cbar.norm.vmin
        perc = 0.03
        if event.button==1:
            self.cbar.norm.vmin -= (perc*scale)*np.sign(dy)
            self.cbar.norm.vmax -= (perc*scale)*np.sign(dy)
        elif event.button==3:
            self.cbar.norm.vmin -= (perc*scale)*np.sign(dy)
            self.cbar.norm.vmax += (perc*scale)*np.sign(dy)
        self.cbar.draw_all()
        self.mappable.set_norm(self.cbar.norm)
        self.cbar.patch.figure.canvas.draw()


    def on_release(self, event):
        """on release we reset the press data"""
        self.press = None
        self.mappable.set_norm(self.cbar.norm)
        self.cbar.patch.figure.canvas.draw()

    def disconnect(self):
        """disconnect all the stored connection ids"""
        self.cbar.patch.figure.canvas.mpl_disconnect(self.cidpress)
        self.cbar.patch.figure.canvas.mpl_disconnect(self.cidrelease)
        self.cbar.patch.figure.canvas.mpl_disconnect(self.cidmotion)
