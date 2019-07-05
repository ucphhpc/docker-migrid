import imageio
import numpy as np
from matplotlib import pyplot

# Read reconstructed image
rec = imageio.imread('phantom_reconstructed.tiff')

pyplot.figure(1)
pyplot.imshow(rec)

# Initial threshold segmentation
threshold = np.max(rec) - np.std(rec) * 3
copy_rec = np.copy(rec)
copy_rec[copy_rec < threshold] = 0.0

# second threshold segmentation
threshold = np.mean(copy_rec[copy_rec > 0]) - np.std(copy_rec)
copy_rec[copy_rec < threshold] = 0.0

pyplot.figure(2)
pyplot.imshow(copy_rec)

# Save segemented image
imageio.imsave('phantom_segmented.tiff', copy_rec)