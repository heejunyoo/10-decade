
import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import urllib.request

# --- Architectures (Standard MTCNN) ---

class PNet(nn.Module):
    def __init__(self):
        super(PNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 10, kernel_size=3)
        self.prelu1 = nn.PReLU(10)
        self.pool1 = nn.MaxPool2d(2, 2, ceil_mode=True)
        self.conv2 = nn.Conv2d(10, 16, kernel_size=3)
        self.prelu2 = nn.PReLU(16)
        self.conv3 = nn.Conv2d(16, 32, kernel_size=3)
        self.prelu3 = nn.PReLU(32)
        self.conv4_1 = nn.Conv2d(32, 2, kernel_size=1)
        self.conv4_2 = nn.Conv2d(32, 4, kernel_size=1)

    def forward(self, x):
        x = self.conv1(x)
        x = self.prelu1(x)
        x = self.pool1(x)
        x = self.conv2(x)
        x = self.prelu2(x)
        x = self.conv3(x)
        x = self.prelu3(x)
        a = self.conv4_1(x)
        b = self.conv4_2(x)
        return b, a # Box, Prob (Standard return order for facenet-pytorch weights?) -> Checked: returns (box, prob) usually or (prob, box). 
        # Facenet-pytorch source says: return a, b (prob, box). 
        # Wait, let's verify weights loading. If I load weights, I must match logic.
        # Let's assume standard order and verify with output shape.
        
class RNet(nn.Module):
    def __init__(self):
        super(RNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 28, kernel_size=3)
        self.prelu1 = nn.PReLU(28)
        self.pool1 = nn.MaxPool2d(3, 2, ceil_mode=True)
        self.conv2 = nn.Conv2d(28, 48, kernel_size=3)
        self.prelu2 = nn.PReLU(48)
        self.pool2 = nn.MaxPool2d(3, 2, ceil_mode=True)
        self.conv3 = nn.Conv2d(48, 64, kernel_size=2)
        self.prelu3 = nn.PReLU(64)
        self.dense4 = nn.Linear(576, 128)
        self.prelu4 = nn.PReLU(128)
        self.dense5_1 = nn.Linear(128, 2)
        self.dense5_2 = nn.Linear(128, 4)

    def forward(self, x):
        x = self.conv1(x)
        x = self.prelu1(x)
        x = self.pool1(x)
        x = self.conv2(x)
        x = self.prelu2(x)
        x = self.pool2(x)
        x = self.conv3(x)
        x = self.prelu3(x)
        x = x.permute(0, 3, 2, 1).contiguous()
        x = self.dense4(x.view(x.shape[0], -1))
        x = self.prelu4(x)
        a = self.dense5_1(x)
        b = self.dense5_2(x)
        return b, a

class ONet(nn.Module):
    def __init__(self):
        super(ONet, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3)
        self.prelu1 = nn.PReLU(32)
        self.pool1 = nn.MaxPool2d(3, 2, ceil_mode=True)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3)
        self.prelu2 = nn.PReLU(64)
        self.pool2 = nn.MaxPool2d(3, 2, ceil_mode=True)
        self.conv3 = nn.Conv2d(64, 64, kernel_size=3)
        self.prelu3 = nn.PReLU(64)
        self.pool3 = nn.MaxPool2d(2, 2, ceil_mode=True)
        self.conv4 = nn.Conv2d(64, 128, kernel_size=2)
        self.prelu4 = nn.PReLU(128)
        self.dense5 = nn.Linear(1152, 256)
        self.prelu5 = nn.PReLU(256)
        self.dense6_1 = nn.Linear(256, 2)
        self.dense6_2 = nn.Linear(256, 4)
        self.dense6_3 = nn.Linear(256, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = self.prelu1(x)
        x = self.pool1(x)
        x = self.conv2(x)
        x = self.prelu2(x)
        x = self.pool2(x)
        x = self.conv3(x)
        x = self.prelu3(x)
        x = self.pool3(x)
        x = self.conv4(x)
        x = self.prelu4(x)
        x = x.permute(0, 3, 2, 1).contiguous()
        x = self.dense5(x.view(x.shape[0], -1))
        x = self.prelu5(x)
        a = self.dense6_1(x)
        b = self.dense6_2(x)
        c = self.dense6_3(x)
        return b, c, a # Box, Landmark, Prob

# --- Main Export Logic ---

def build_and_export():
    save_dir = "models/onnx/mtcnn"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    base_url = "https://github.com/timesler/facenet-pytorch/raw/master/data"
    
    # 1. P-Net
    print("Processing P-Net...")
    pnet = PNet()
    pnet_w_path = "pnet.pt"
    if not os.path.exists(pnet_w_path):
        print("  Downloading weights...")
        urllib.request.urlretrieve(f"{base_url}/pnet.pt", pnet_w_path)
    pnet.load_state_dict(torch.load(pnet_w_path, map_location='cpu'))
    pnet.eval()
    
    # Facenet-pytorch PNet forward: returns (prob, box)
    # My class above: returns (box, prob)
    # WAIT! Creating compat helper to match weights.
    # The weights 'conv4_1' (2ch) is prob? 'conv4_2' (4ch) is box?
    # Checking source...
    # In facenet-pytorch: conv4_1 is classified (2), conv4_2 is bbox (4).
    # Forward: a = conv4_1(x), b = conv4_2(x). Return a, b.
    # So PNet returns (Prob, Box).
    # Let's adjust Forward to match expected ONNX logical names.
    
    class PNetWrapper(nn.Module):
        def __init__(self, original):
            super().__init__()
            self.model = original
        def forward(self, x):
            b, a = self.model(x) # My class returns Box, Prob
            # We want Prob (2), Box(4) usually? 
            # Or just output whatever and name it correctly.
            # My Code: 4_1 is 2ch (Prob). 4_2 is 4ch (Box).
            # My Forward: a=4_1(Prob), b=4_2(Box). Returns b(Box), a(Prob).
            # So output 0 is Box, output 1 is Prob.
            return a, b # Return Prob, Box
            
    pnet_wrap = PNetWrapper(pnet)
    
    torch.onnx.export(
        pnet_wrap,
        torch.randn(1, 3, 48, 48),
        os.path.join(save_dir, "pnet.onnx"),
        input_names=['input'],
        output_names=['prob', 'box'], # 0=Prob, 1=Box
        dynamic_axes={'input': {2: 'height', 3: 'width'}, 'prob': {2: 'h', 3: 'w'}, 'box': {2: 'h', 3: 'w'}},
        opset_version=11
    )
    print("✅ P-Net Exported")
    
    # 2. R-Net
    print("Processing R-Net...")
    rnet = RNet()
    rnet_w_path = "rnet.pt"
    if not os.path.exists(rnet_w_path):
        urllib.request.urlretrieve(f"{base_url}/rnet.pt", rnet_w_path)
    rnet.load_state_dict(torch.load(rnet_w_path, map_location='cpu'))
    rnet.eval()
    
    # My Class: dense5_1 is 2ch (Prob). dense5_2 is 4ch (Box).
    # Forward: returns b(Box), a(Prob).
    class RNetWrapper(nn.Module):
        def __init__(self, original):
            super().__init__()
            self.model = original
        def forward(self, x):
            b, a = self.model(x)
            return a, b # Prob, Box
            
    rnet_wrap = RNetWrapper(rnet)
    
    torch.onnx.export(
        rnet_wrap,
        torch.randn(1, 3, 24, 24),
        os.path.join(save_dir, "rnet.onnx"),
        input_names=['input'],
        output_names=['prob', 'box'],
        dynamic_axes={'input': {0: 'batch'}, 'prob': {0: 'batch'}, 'box': {0: 'batch'}},
        opset_version=11
    )
    print("✅ R-Net Exported")
    
    # 3. O-Net
    print("Processing O-Net...")
    onet = ONet()
    onet_w_path = "onet.pt"
    if not os.path.exists(onet_w_path):
        urllib.request.urlretrieve(f"{base_url}/onet.pt", onet_w_path)
    onet.load_state_dict(torch.load(onet_w_path, map_location='cpu'))
    onet.eval()
    
    # My Class: 6_1(2ch Prob), 6_2(4ch Box), 6_3(10ch Points)
    # Forward: returns b(Box), c(Points), a(Prob)
    class ONetWrapper(nn.Module):
        def __init__(self, original):
            super().__init__()
            self.model = original
        def forward(self, x):
            b, c, a = self.model(x)
            return a, b, c # Prob, Box, Points
            
    onet_wrap = ONetWrapper(onet)
    
    torch.onnx.export(
        onet_wrap,
        torch.randn(1, 3, 48, 48),
        os.path.join(save_dir, "onet.onnx"),
        input_names=['input'],
        output_names=['prob', 'box', 'landmarks'],
        dynamic_axes={'input': {0: 'batch'}, 'prob': {0: 'batch'}, 'box': {0: 'batch'}, 'landmarks': {0: 'batch'}},
        opset_version=11
    )
    print("✅ O-Net Exported")
    
    # Cleanup
    for f in [pnet_w_path, rnet_w_path, onet_w_path]:
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    build_and_export()
