#########
##  Functions for generatign artificial data: adding blur and noise to segmented data, write parameters to file
##
import numpy as np
import itertools

from arcmodelling_IDMC import model_functions as mf
from arcmodelling_IDMC import tools

def add_blur_and_noise(data, params):
    '''adding blurr and noise in all different orders:
    if parameter=0, this step is skipped'''

    data_b_n=data.copy()

    if params['sigma_b']:
        data_b_n = snd.gaussian_filter(data_b_n, sigma=params['sigma_b'])
    if params['sigma_n']:
        data_b_n += np.random.normal(0, scale=params['sigma_n'], size=np.shape(data_b_n))
    if params['sigma_b2']:
        data_b_n = snd.gaussian_filter(data_b_n, sigma=params['sigma_b2'])

    return data_b_n


def add_I(data_segm, params):
    '''data_segm must have labels 1, 2, ...N for up to N=255 labels'''
    data_I = np.zeros_like(data_segm, dtype=np.float64)

    for i, Ii in enumerate(params['I']):
        data_I[data_segm==(i+1)]+=Ii
    return data_I



def write_param_file(dataset_path, dataset_name, params, N, R=0, sampled=False):
    '''Saves file with info from params dict'''

    with open(dataset_path+dataset_name+'_params.txt', 'w') as fileid:
        fileid.write('################\n')
        fileid.write('#### PARAMS ####\n')
        fileid.write('################\n\n')
        fileid.write('#### Dataset: %s ####\n'%(dataset_name))
        fileid.write('#### N: %i ####\n'%(N))
        if R:
            fileid.write('#### R: %.4f ####\n\n'%(R))

        Istring='I '
        for Ii in params['I']:
            Istring += str(Ii)+' '
        fileid.write(Istring+'\n')

        fileid.write('sigma_b '+str(params['sigma_b'])+'\n')
        fileid.write('sigma_n '+str(params['sigma_n'])+'\n')
        fileid.write('sigma_b2 '+str(params['sigma_b2'])+'\n\n')

        if sampled:
            fileid.write('#### Sampled weights:  \n\n')
        else:
            fileid.write('#### Weights found by counting masks: \n\n')
            
        wstring='w '
        for wi in params['w']:
            wstring += str(wi)+' '
        fileid.write(wstring+'\n')


def read_param_file(data_filename=''):
    '''Reads file with info to params dict'''

    params={}

    with open(data_filename+'_params.txt', 'r') as fileid:
        for line in fileid.readlines():
            if not line.startswith('#'):
                if line.strip(): #not blank

                    if line.startswith('I'):
                        params['I']=[float(Ii) for Ii in line.strip().split()[1:]]

                    elif line.startswith('w'):
                        params['w']=[float(wi) for wi in line.strip().split()[1:]]

                    else:
                        key, param = line.strip().split()
                        params[key]=float(param)
    return params

###############
### SPHERES ###
###############

def generate_centerdist_vol(N, offset=np.array([0.056234, 0.0234264, -0.06546])):
    '''Create volume with each voxel filled with the radial distance to the center.
    offset: a 3 element vector with values between -0.5 and 0.5 that describes an offset of the center of the phere
    form the center of a voxel - avoid surface lining up with voxel edges..'''

    sphere_center = offset + N/2

    # % create three coordinate cubes where each element contains the x,y or z coordinate of the corresponding voxel location.
    x1, x2, x3 = np.meshgrid(np.arange(int(N)), np.arange(int(N)), np.arange(int(N)))

    # % calculate the distance to the sphere at every location in the domain.
    # % (LATER: subtract the radius to have the surface where the values cross zero.)
    centerdist_vol = np.sqrt((np.ones((N,N,N))*sphere_center[0]- x1)**2 + \
                             (np.ones((N,N,N))*sphere_center[1] - x2)**2 + \
                             (np.ones((N,N,N))*sphere_center[2] - x3)**2 )


    print('Volume size: '+str((N, N, N)))
    print('Gives '+str(N**3)+' voxels')

    return centerdist_vol



def generate_Ivol(centerdist_vol, params, I1_ind, I2_ind, R=None):

    N=np.shape(centerdist_vol)[0] #shape N*N*N
    Rmax = R if R is not None else N/2 - 4*params['sigma_b'] - 2 #"safety buffer" of 2 voxels

    print('Volume generated, R= ', Rmax)

    Ivol = mf.I_np(centerdist_vol-Rmax, params['I'][I1_ind], params['I'][I2_ind], sigma_b=params['sigma_b'])

    return Ivol







def generate_all_Ivols(centerdist_vol, params, volumes_path):
    '''Generates volumes for all combinations of Is in params['I']
    Adds noise
    Saves intensity data and gradient data'''

    I_inds = range(len(params['I']))

    #iterate over I to get all combinations
    for a in I_inds:
        for b in I_inds:
            if a!=b: #whenever they are not equal
                vol_temp=generate_Ivol(centerdist_vol, params, a, b)
                #add noise
                vol_temp+=np.random.normal(0, params['sigma_n'], size=np.shape(vol_temp))
                np.save(volumes_path+'vol_intensity_'+str(a)+str(b)+'.npy', vol_temp.astype(np.float32))
                #calculate gradient
                vol_temp_grad=tools.gradient3D(vol_temp)
                np.save(volumes_path+'vol_gradient_'+str(a)+str(b)+'.npy', vol_temp_grad.astype(np.float32))


def generate_all_datasets(params, volumes_path, datasets_path, masks):
    ''' Interface Ia_Ib and Ib_Ia combined in final data_IaIb to have symmetric interface components
        Interior phase Ia made from Ia_Ib interior and Ia_Ic interior,
                                    Ia_Ib exterior and Ia_Ic exterior combined  ...
                                    (ikkje vits kanskje, samplar jo uansett meget lite herifra, jaja) '''

    interface_mask, interior_mask, exterior_mask = masks

    #remove outer layer to only include grad calculated by central diff
    interface_mask=interface_mask[1:-1, 1:-1, 1:-1]
    interior_mask=interior_mask[1:-1, 1:-1, 1:-1]
    exterior_mask=exterior_mask[1:-1, 1:-1, 1:-1]

    I_inds = range(len(params['I']))

    #iterate over I to get all combinations:

    # ##SAVE PHASE INTERIOR DATASETS
    for a in I_inds:
        dataset_phase_interior_temp = []
        dataset_phase_interior_grad_temp = []
        for b in I_inds:
            if a!=b: #whenever they are not equal
                vol=np.load(volumes_path+'vol_intensity_'+str(a)+str(b)+'.npy')
                vol=vol[1:-1, 1:-1, 1:-1]
                vol_interior = vol[interior_mask]
                dataset_phase_interior_temp.append(vol_interior)
                vol=np.load(volumes_path+'vol_intensity_'+str(b)+str(a)+'.npy')
                vol=vol[1:-1, 1:-1, 1:-1]
                vol_exterior = vol[exterior_mask]
                dataset_phase_interior_temp.append(vol_exterior)

                vol=np.load(volumes_path+'vol_gradient_'+str(a)+str(b)+'.npy')
                vol=vol[1:-1, 1:-1, 1:-1]
                vol_interior = vol[interior_mask]
                dataset_phase_interior_grad_temp.append(vol_interior)
                vol=np.load(volumes_path+'vol_gradient_'+str(b)+str(a)+'.npy')
                vol=vol[1:-1, 1:-1, 1:-1]
                vol_exterior = vol[exterior_mask]
                dataset_phase_interior_grad_temp.append(vol_exterior)

        np.save(datasets_path+'data_intensity_'+str(a)+'.npy', np.concatenate(dataset_phase_interior_temp))
        np.save(datasets_path+'data_gradient_'+str(a)+'.npy', np.concatenate(dataset_phase_interior_grad_temp))


    ##SAVE INTERFACE DATASETS
    for a, b in list(itertools.combinations(I_inds, 2)): #iterate over all interfaces

        dataset_interface_temp = []

        vol=np.load(volumes_path+'vol_intensity_'+str(a)+str(b)+'.npy')
        vol=vol[1:-1, 1:-1, 1:-1]
        vol_interface = vol[interface_mask]
        dataset_interface_temp.append(vol_interface)

        vol=np.load(volumes_path+'vol_intensity_'+str(b)+str(a)+'.npy')
        vol=vol[1:-1, 1:-1, 1:-1]
        vol_interface = vol[interface_mask]
        dataset_interface_temp.append(vol_interface)

        np.save(datasets_path+'data_intensity_'+str(a)+str(b)+'.npy', np.concatenate(dataset_interface_temp))



        dataset_interface_grad_temp = []

        vol=np.load(volumes_path+'vol_gradient_'+str(a)+str(b)+'.npy')
        vol=vol[1:-1, 1:-1, 1:-1]
        vol_interface = vol[interface_mask]
        dataset_interface_grad_temp.append(vol_interface)

        vol=np.load(volumes_path+'vol_gradient_'+str(b)+str(a)+'.npy')
        vol=vol[1:-1, 1:-1, 1:-1]
        vol_interface = vol[interface_mask]
        dataset_interface_grad_temp.append(vol_interface)

        np.save(datasets_path+'data_gradient_'+str(a)+str(b)+'.npy', np.concatenate(dataset_interface_grad_temp))






###below only for I0 interior, I1 exterior

def get_masks(Ivol, params, wb):
    interface_mask=(Ivol>mf.I_np(-params['sigma_b']*wb, params['I'][0], params['I'][1], params['sigma_b'])) \
                  *(Ivol<mf.I_np( params['sigma_b']*wb, params['I'][0], params['I'][1], params['sigma_b']))
    interior_mask=(Ivol<=mf.I_np(-params['sigma_b']*wb, params['I'][0], params['I'][1], params['sigma_b']))
    exterior_mask=(Ivol>=mf.I_np( params['sigma_b']*wb, params['I'][0], params['I'][1], params['sigma_b']))

    return interface_mask, interior_mask, exterior_mask





def sample_dataset(datasets_path, dataset_size, weights):
    '''Creates dataset by sampling uniformly from already generated datasets according to weights'''

    nsamples = [int(w*dataset_size) for w in weights]
    print('Number of samples from each dataset: \n', nsamples)


    Ii = [str(i) for i in range(int(len(weights)/2))]
    Iij = [str(a)+str(b) for a, b in list(itertools.combinations(Ii, 2))]

    component_names = Ii + Iij

    dataset_intensity=[]
    dataset_gradient=[]

    for i, c_name in enumerate(component_names):

        print('Sampling ', str(c_name), '...\n')

        ##INTERIORS
        data_i=np.load(datasets_path+'data_intensity_'+str(c_name)+'.npy')
        data_g=np.load(datasets_path+'data_gradient_'+c_name+'.npy')

        inds=np.random.randint(0, len(data_i), nsamples[i])

        dataset_intensity.append(data_i[inds])
        dataset_gradient.append(data_g[inds])

    return np.concatenate(dataset_intensity), np.concatenate(dataset_gradient)
