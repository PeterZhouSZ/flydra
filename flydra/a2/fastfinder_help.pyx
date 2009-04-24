import numpy as np
cimport numpy as np

import cython

@cython.boundscheck(False) # turn of bounds-checking for entire function
def get_first_idx(np.ndarray[long, ndim=1] haystack, np.ndarray[long, ndim=1] needles):

    # TODO: implementation that does binary search on pre-sorted
    # haystack

    assert haystack.ndim==1
    assert needles.ndim==1

    cdef long hmax = haystack.shape[0]
    cdef long nmax = needles.shape[0]
    cdef long i,j
    cdef int needle_found
    cdef np.ndarray[long, ndim=1] found

    found = np.zeros( (needles.shape[0],) , dtype=np.int)

    for i in range(nmax):
        needle_found = 0
        for j in range(hmax):
            if haystack[j]==needles[i]:
                needle_found=1
                break
        if needle_found:
            found[i] = j
        else:
            found[i] = -1

    if np.any(found==-1):
        raise ValueError('some of your needles were not found')

    return found
