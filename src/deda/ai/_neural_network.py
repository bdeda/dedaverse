
import os

import torch
import pandas

from torch.utils.data import Dataset
from torch import nn
from torch.utils.data import DataLoader
#from torchvision import datasets, transforms


class UsdDataset(Dataset):
    def __init__(self, annotations_file, rootdir, transform=None, target_transform=None):
        self._labels = pandas.read_csv(annotations_file)
        self._rootdir = rootdir
        self._transform = transform
        self._target_transform = target_transform

    def __len__(self):
        return len(self.img_labels)

    def __getitem__(self, idx):
        data_path = os.path.join(self._rootdir, self._labels.iloc[idx, 0])
        image = decode_image(img_path)
        label = self.img_labels.iloc[idx, 1]
        if self.transform:
            image = self.transform(image)
        if self.target_transform:
            label = self.target_transform(label)
        return image, label


class NeuralNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.flatten = nn.Flatten()
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(28*28, 512),
            nn.ReLU(),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Linear(512, 10),
        )

    def forward(self, x):
        x = self.flatten(x)
        logits = self.linear_relu_stack(x)
        return logits