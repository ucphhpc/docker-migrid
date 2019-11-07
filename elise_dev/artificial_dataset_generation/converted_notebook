#!/usr/bin/env python
# coding: utf-8

# In[6]:


import numpy as np
import os

#LOCAL imports
from arcmodelling_IDMC import artificial_data_gen as adgen
from arcmodelling_IDMC import tools


# # 1. Create volume with center distances

# ## Default parameters

# In[14]:


N=100
dataset_path = 'N'+str(N) #where stuff will be saved


# In[15]:


if not os.path.exists(dataset_path):
    os.makedirs(dataset_path)


# ## Generate data

# In[16]:


centerdist_vol = adgen.generate_centerdist_vol(N)


# ## (Plotting)

# In[17]:


tools.plot_center_slices(centerdist_vol)


# ## Save data

# In[18]:


np.save(os.path.join(dataset_path, 'centerdist_vol.npy'), centerdist_vol)


# In[ ]:




