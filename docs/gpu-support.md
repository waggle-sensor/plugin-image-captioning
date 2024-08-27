# GPU Support on Nvidia Jetson

The biggest problem on running the Florence2 model on Jetson GPU is the version incompatibility between PyTorch and CUDA version. PyTorch is usually compiled on a specific CUDA version, and machine learning libraries such as transformer and flash attention require a recent version of PyTorch. Because of this chained dependency, the latest JetPack is highly recommended.

## JetPack 6.x
As of Aug 2024, Nvidia ceased to publish l4t-pytorch NGC containers for JetPack 6.x. Instead, they recommend using the CUDA base container and install Pytorch (See [more](https://forums.developer.nvidia.com/t/jetpack-6-0-production-release-announcement/291709/2)). The [Dockerfile](gpu/Dockerfile.jp60-cuda122) installs Pytorch and other libraries on top of JetPack container.

## JetPack 5.x
JetPack 5.1.2 with CUDA 11.4 does not support the flash attention library, which requires CUDA 11.6. We found a custom container "shubhamgupto/jp5.1-cuda11.8-cudnn9-trt8.5" which has CUDA 11.8 for JetPack 5.1. Using it and installing PyTorch and other libraries on top of this container image make the code runnable (see more in the [Dockerfile](gpu/Dockerfile.jp51-cuda118)).

## JetPack 4.x
Because of the PyTorch and flash attention libraries requiring higher CUDA than what JetPack 4 has, it is not possible to run the code, unless someone finds a way to install higher version of CUDA or making the libraries compatible with CUDA 10.x.