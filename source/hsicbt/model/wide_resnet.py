import torch
import torch.nn as nn
import torch.nn.init as init
import torch.nn.functional as F
from torch.autograd import Variable
from torchsummary import summary

import sys
import numpy as np

def conv3x3(in_planes, out_planes, stride=1):
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=True)

def conv_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        init.xavier_uniform_(m.weight, gain=np.sqrt(2))
        init.constant_(m.bias, 0)
    elif classname.find('BatchNorm') != -1:
        init.constant_(m.weight, 1)
        init.constant_(m.bias, 0)

class wide_basic(nn.Module):
    def __init__(self, in_planes, planes, dropout_rate, stride=1):
        super(wide_basic, self).__init__()
        self.bn1 = nn.BatchNorm2d(in_planes)
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, padding=1, bias=True)
        self.dropout = nn.Dropout(p=dropout_rate)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=True)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, planes, kernel_size=1, stride=stride, bias=True),
            )

    def forward(self, x):
        # Tong added for hsic trainining
        if isinstance(x, tuple):
            x, output_list = x
        else:
            output_list = []
        # Tong added ends
        
        out = self.dropout(self.conv1(F.relu(self.bn1(x))))
        out = self.conv2(F.relu(self.bn2(out)))
        out += self.shortcut(x)

        output_list.append(out)
        
        return out, output_list

class WideResNet(nn.Module):
    def __init__(self, depth, widen_factor, dropout_rate, num_classes, rob=False, shrink=1):
        super(WideResNet, self).__init__()
        self.in_planes = 16

        assert ((depth-4)%6 ==0), 'Wide-resnet depth should be 6n+4'
        n = (depth-4)/6
        k = widen_factor

        print('| Wide-Resnet %dx%d' %(depth, k))
        nStages = [16, 16*k, 32*k, 64*k]

        self.conv1 = conv3x3(3,int(nStages[0]* shrink))
        self.layer1 = self._wide_layer(wide_basic, int(nStages[1]* shrink), n, dropout_rate, stride=1)
        self.layer2 = self._wide_layer(wide_basic, int(nStages[2]* shrink), n, dropout_rate, stride=2)
        self.layer3 = self._wide_layer(wide_basic, int(nStages[3]* shrink), n, dropout_rate, stride=2)
        self.bn1 = nn.BatchNorm2d(int(nStages[3]* shrink), momentum=0.9)
        self.linear = nn.Linear(int(nStages[3]* shrink), num_classes)

        self.rob = rob
        
    def _wide_layer(self, block, planes, num_blocks, dropout_rate, stride):
        strides = [stride] + [1]*(int(num_blocks)-1)
        layers = []

        for stride in strides:
            layers.append(block(self.in_planes, planes, dropout_rate, stride))
            self.in_planes = planes

        return nn.Sequential(*layers)

    def forward(self, x):
        output_list = []
        
        out = self.conv1(x)
        output_list.append(out)
        
        out, out_list = self.layer1(out)
        output_list.extend(out_list)
        
        out, out_list = self.layer2(out)
        output_list.extend(out_list)
            
        out, out_list = self.layer3(out)
        output_list.extend(out_list)
            
        out = F.relu(self.bn1(out))
        out = F.avg_pool2d(out, 8)
        out = out.view(out.size(0), -1)
        output_list.append(out)
        
        out = self.linear(out)
        
        if self.rob:
            return out
        else:
            return out, output_list

def WideResNet28_10(**kwargs):
    rob = kwargs['robustness'] if 'robustness' in kwargs else False
    shrink = kwargs['shrink'] if 'shrink' in kwargs else 1
    return WideResNet(28, 10, 0, kwargs['num_classes'], rob=rob, shrink=shrink)

def WideResNet28_4(**kwargs):
    rob = kwargs['robustness'] if 'robustness' in kwargs else False
    shrink = kwargs['shrink'] if 'shrink' in kwargs else 1
    return WideResNet(28, 4, 0, kwargs['num_classes'], rob=rob, shrink=shrink)

if __name__ == '__main__':
    net=WideResNet(28, 10, 0, 100, True, 1)
    #y = net(Variable(torch.randn(1,3,32,32)))
    #print(y.size())
    summary(net.cuda(), (3,32,32))
    