# Cryo-EM image simulation and analysis powered by JAX.
This library is a modular framework for simulating forward models of cryo electron microscopy images. It is designed with 2D template matching analysis in mind, but it can be used generally. `cryojax` is, of course, built on [JAX](https://github.com/google/jax).

## Summary

The core of this package is its ability to simulate cryo-EM images. Starting with a 3D electron density map, one can simulate a scattering process onto the imaging plane with modulation by the instrument optics. Images are then sampled from models of the noise or the corresponding log-likelihood is computed.

These models can be fed into standard statistical inference or optimization libraries in `jax`, such as [numpyro](https://github.com/pyro-ppl/numpyro) or [jaxopt](https://github.com/google/jaxopt).

## Installation

Installing `cryojax` is currently a bit more complicated than it should be because it relies on the library [tensorflow-nufft](https://github.com/mrphys/tensorflow-nufft) through the `jax` experimental feature [jax2tf](https://github.com/google/jax/blob/main/jax/experimental/jax2tf/README.md). Getting [tensorflow](https://github.com/tensorflow/tensorflow) to install besides `jax` is a bit of a pain. Once [jax-finufft](https://github.com/dfm/jax-finufft) adds GPU support, the `tensorflow` dependency will be replaced. In the following instructions, please install `tensorflow` and `jax` with either GPU or CPU support.

To start, I recommend creating a new virtual environment. For example, you could do this with `conda`.

```bash
conda create -n cryojax -c conda-forge python=3.10
```

Note that `python>=3.10` is required because of recent features in [dataclasses](https://docs.python.org/3/library/dataclasses.html) support. Custom dataclasses that are safe to pass to `jax` are heavily used in this library!

Then, modify the [tensorflow installation](https://www.tensorflow.org/install/pip) instructions to install version 2.11.x. As I'm writing this, `tensorflow-nufft` supports up to version 2.11.x, which is tested on `3.7<=python<=3.10`. `tensorflow>=2.12.x` and `python>=3.11` may not be supported.

Now [install tensorflow-nufft](https://mrphys.github.io/tensorflow-nufft/guide/start/) with

```bash
pip install tensorflow-nufft==0.12.0
```

Next, [install JAX](https://github.com/google/jax#installation). I have found it easier to first install `tensorflow` and then `jax` because each try to install their own CUDA dependencies. `tensorflow` seems to be more strict about this.

Finally, install `cryojax`. For now, only a source build is supported.

```bash
git clone https://github.com/mjo22/cryojax
cd cryojax
python -m pip install .
```

This will install the remaining dependencies, such as [jaxlie](https://github.com/brentyi/jaxlie) for coordinate rotations and translations, [mrcfile](https://github.com/ccpem/mrcfile) for I/O, and [dataclasses-json](https://github.com/lidatong/dataclasses-json) for serialization.

## Usage

Please note that this library is currently experimental and the API is subject to change!

The following is a basic workflow to generate an image with a gaussian white noise model.

First, instantiate the image formation method ("scattering") and its respective representation
of an electron density ("specimen").

```python
import jax
import cryojax.simulator as cs

template = "example.mrc"
scattering = cs.NufftScattering(shape=(320, 320))
specimen = cs.ElectronCloud.from_file(template, resolution=1.1)
```

Here, `template` is a 3D electron density map in MRC format. This could be taken from the [EMDB](https://www.ebi.ac.uk/emdb/), or rasterized from a [PDB](https://www.rcsb.org/). [cisTEM](https://github.com/timothygrant80/cisTEM) provides an excellent rasterization tool in its image simulation program. In the above example, a rasterzied grid is converted to a density point cloud with the `ElectronCloud` autoloader. Alternatively, a user could call the `ElectronCloud` constructor. This is loaded in real-space and pairs with ``NufftScattering``, which rasterizes images using [non-uniform FFTs](https://github.com/mrphys/tensorflow-nufft). Alternatively, one could load the volume in fourier space and use the fourier-slice projection theorem.

```python
scattering = cs.FourierSliceScattering(shape=(320, 320))
specimen = cs.ElectronGrid.from_file(template, resolution=1.1)
```

Next, the model is configured at initial `Pose`, `Optics`, and `Detector` parameters.
Then, an `Image` model is chosen. Here, we choose `GaussianImage`.

```python
key = jax.random.PRNGKey(seed=0)
pose, optics, detector = cs.EulerPose(), cs.CTFOptics(), cs.WhiteNoiseDetector(key=key, pixel_size=1.1)
state = cs.PipelineState(pose=pose, optics=optics, detector=detector)
model = cs.GaussianImage(scattering=scattering, specimen=specimen, state=state)
image = model()
```

This computes an image at the instantiated model configuration. We can then compute the model at a set of updated parameters using python keyword arguments.

```python
params = dict(view_phi=180, defocus_u=8000., pixel_size=1.09)
image = model(**params)
```

This workflow evaulates it at a state with an updated viewing angle `view_phi`, major axis defocus `defocus_u`, and detector pixel size `pixel_size`. If we want to get a new model at these updated parameters, we can simply call the `model.update` method.

```python
model = model.update(**params)
```

This method is inherited from the `cryojax` base class, `CryojaxObject`. The intention is to make it simple to work with nested class structures!

Imaging models also accept a series of `Filter`s and `Mask`s. For example, one could add a `LowpassFilter`, `WhiteningFilter`, and a `CircularMask`.

```python
from cryojax.utils import fftfreqs

filters = [cs.LowpassFilter(scattering.freqs, cutoff=0.667),  # Cutoff modes above 2/3 Nyquist frequency
           cs.WhiteningFilter(scattering.freqs, fftfreqs(micrograph.shape), micrograph)]
masks = [cs.CircularMask(scattering.coords, radius=1.0)]      # Cutoff pixels above radius equal to (half) image size
model = cs.GaussianImage(scattering=scattering, specimen=specimen, state=state, filters=filters, masks=masks)
image = model(**params)
```

If a `GaussianImage` is initialized with the field `observed`, the model will instead compute a Gaussian log-likelihood in Fourier space with a diagonal covariance tensor (or power spectrum).

```python
model = cs.GaussianImage(scattering=scattering, specimen=specimen, state=state, observed=observed)
log_likelihood = model(**params)
```

Note that the user may need to do preprocessing of `observed`, such as applying the relevant `Filter`s and `Mask`s. `jax` functional transformations can now be applied to the model!

```python
@jax.jit
@jax.value_and_grad
def loss(params):
    return model(**params)
```

Note that in order to jit-compile the `model` we must create a wrapper for it because it is a `dataclass`, not a function. Alternatively, one could create a custom loss function from calling `Image` methods directly, such as `Image.render`.

Additional components can be plugged into the `Image` model's `PipelineState`. For example, `Ice` models are supported. For example, `EmpiricalIce` stores an empirical measure of the ice power spectrum. `ExponentialNoiseIce` generates ice as noise whose correlations decay exponentially. Imaging models from different stages of the pipeline are also implemented. `ScatteringImage` computes images solely with the scattering model, while `OpticsImage` uses a scattering and optics model. `DetectorImage` turns this into a detector readout, while `GaussianImage` adds the ability to evaluate a gaussian likelihood.

For these more advanced examples, see the tutorials section of the repository. In general, `cryojax` is designed to be very extensible and new models can easily be implemented.

## Features

Imaging models in `cryojax` support `jax` functional transformations, such as automatic differentiation with `grad`, paralellization with `vmap` and `pmap`, and just-in-time compilation with `jit`. Models also support GPU/TPU acceleration. Until GPU support for `jax-finufft` is added, models using the `NufftScattering` method will not support `jit`, `vmap`, and `pmap`. This is because `tensorflow-nufft` does not compile.

## Similar libraries

- [cisTEM](https://github.com/timothygrant80/cisTEM): A software to process cryo-EM images of macromolecular complexes and obtain high-resolution 3D reconstructions from them. The recent experimental release of `cisTEM` has implemented a successful 2DTM program.

- [BioEM](https://github.com/bio-phys/BioEM): Bayesian inference of Electron Microscopy. This codebase calculates the posterior probability of a structural model given multiple experimental EM images.

## Acknowledgments

The tooling, packaging structure, and API in `cryojax` are influenced by the library [tinygp](https://github.com/dfm/tinygp), which is also written in `jax` and makes use of custom, jax-friendly python `dataclasses`. Thank you for the developers for providing an excellent model for this package!
