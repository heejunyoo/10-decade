
import os
import torch
from facenet_pytorch import MTCNN, PNet, RNet, ONet

def export_mtcnn():
    # Initialize models
    pnet = PNet()
    rnet = RNet()
    onet = ONet()
    
    # Load weights (facenet-pytorch automaticaly loads pretrained on init)
    pnet.eval()
    rnet.eval()
    onet.eval()
    
    save_dir = "models/onnx/mtcnn"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    print(f"Exporting models to {save_dir}...")
    
    # 1. Export P-Net
    # Input: [Batch, 3, H, W] -> Dynamic H, W
    dummy_input_p = torch.randn(1, 3, 48, 48) 
    pnet_path = os.path.join(save_dir, "pnet.onnx")
    torch.onnx.export(
        pnet, 
        dummy_input_p, 
        pnet_path,
        input_names=['input'],
        output_names=['probs', 'offsets'], # Conf, Box
        dynamic_axes={'input': {2: 'height', 3: 'width'}},
        opset_version=11
    )
    print("✅ P-Net Exported")
    
    # 2. Export R-Net
    # Input: [Batch, 3, 24, 24] -> Fixed
    dummy_input_r = torch.randn(1, 3, 24, 24)
    rnet_path = os.path.join(save_dir, "rnet.onnx")
    torch.onnx.export(
        rnet,
        dummy_input_r,
        rnet_path,
        input_names=['input'],
        output_names=['probs', 'offsets'],
        dynamic_axes={'input': {0: 'batch'}},
        opset_version=11
    )
    print("✅ R-Net Exported")
    
    # 3. Export O-Net
    # Input: [Batch, 3, 48, 48] -> Fixed
    dummy_input_o = torch.randn(1, 3, 48, 48)
    onet_path = os.path.join(save_dir, "onet.onnx")
    torch.onnx.export(
        onet,
        dummy_input_o,
        onet_path,
        input_names=['input'],
        output_names=['probs', 'offsets', 'points'], # Conf, Box, Landmarks
        dynamic_axes={'input': {0: 'batch'}},
        opset_version=11
    )
    print("✅ O-Net Exported")
    
if __name__ == "__main__":
    export_mtcnn()
