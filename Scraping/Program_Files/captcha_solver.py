import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import numpy as np
import string

# Define constants
CHAR_SET = string.ascii_lowercase + string.ascii_uppercase + string.digits  # a-z, A-Z, 0-9
NUM_CLASSES = len(CHAR_SET)  # 26 (a-z) + 26 (A-Z) + 10 (0-9) = 60
CAPTCHA_LENGTH = 5  # Fixed 5 characters
IMG_HEIGHT = 50
IMG_WIDTH = 200
BATCH_SIZE = 32
EPOCHS = 20
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Map characters to indices
char_to_idx = {char: idx for idx, char in enumerate(CHAR_SET)}
idx_to_char = {idx: char for char, idx in char_to_idx.items()}

# Custom Dataset for CAPTCHA images
class CaptchaDataset(Dataset):
    def __init__(self, image_dir, transform=None):
        self.image_dir = image_dir
        self.transform = transform
        self.images = [f for f in os.listdir(image_dir) if f.endswith(('.png', '.jpg'))]
        if len(self.images) < 100:
            raise ValueError(f"Too few images: found {len(self.images)} in {image_dir}, need at least 100")
        
        # Validate filenames
        for img_name in self.images:
            label_str = os.path.splitext(img_name)[0]
            if len(label_str) != CAPTCHA_LENGTH or not all(c in CHAR_SET for c in label_str):
                raise ValueError(f"Invalid filename '{img_name}' in {image_dir}: must be {CAPTCHA_LENGTH} chars from {CHAR_SET}")
        print(f"Found {len(self.images)} valid images in {image_dir}")

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = self.images[idx]
        img_path = os.path.join(self.image_dir, img_name)
        try:
            image = Image.open(img_path).convert('L')  # Grayscale
        except Exception as e:
            raise ValueError(f"Failed to open image {img_path}: {str(e)}")
        
        if self.transform:
            image = self.transform(image)
        
        # Extract label from filename
        label_str = os.path.splitext(img_name)[0]
        label = torch.tensor([char_to_idx[c] for c in label_str], dtype=torch.long)
        return image, label

# Data transformations
transform = transforms.Compose([
    transforms.Resize((IMG_HEIGHT, IMG_WIDTH)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5], std=[0.5])  # Normalize grayscale
])

# CNN Model for CAPTCHA recognition
class CaptchaModel(nn.Module):
    def __init__(self):
        super(CaptchaModel, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool2d(2, 2)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.pool3 = nn.MaxPool2d(2, 2)
        
        # Calculate flattened size: (IMG_HEIGHT//8) * (IMG_WIDTH//8) * 128
        self.flattened_size = (IMG_HEIGHT // 8) * (IMG_WIDTH // 8) * 128
        self.fc = nn.Linear(self.flattened_size, CAPTCHA_LENGTH * NUM_CLASSES)
    
    def forward(self, x):
        x = nn.ReLU()(self.conv1(x))
        x = self.pool1(x)
        x = nn.ReLU()(self.conv2(x))
        x = self.pool2(x)
        x = nn.ReLU()(self.conv3(x))
        x = self.pool3(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.fc(x)
        x = x.view(x.size(0), CAPTCHA_LENGTH, NUM_CLASSES)  # Reshape for per-character logits
        return x

# Training function
def train_model(dataset_path, model_path='captcha_model.pth'):
    # Load dataset
    dataset = CaptchaDataset(image_dir=dataset_path, transform=transform)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    # Initialize model, loss, optimizer
    model = CaptchaModel().to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    # Training loop
    model.train()
    for epoch in range(EPOCHS):
        running_loss = 0.0
        correct = 0
        total = 0
        for images, labels in dataloader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(images)
            
            # Compute loss for each character position
            loss = 0
            for i in range(CAPTCHA_LENGTH):
                loss += criterion(outputs[:, i, :], labels[:, i])
            loss /= CAPTCHA_LENGTH
            
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            
            # Calculate accuracy
            _, predicted = torch.max(outputs, 2)
            correct += (predicted == labels).all(dim=1).sum().item()
            total += labels.size(0)
        
        epoch_loss = running_loss / len(dataloader)
        epoch_acc = correct / total
        print(f"Epoch [{epoch+1}/{EPOCHS}], Loss: {epoch_loss:.4f}, Accuracy: {epoch_acc:.4f}")
    
    # Save the model
    torch.save(model.state_dict(), model_path)
    print(f"Model saved to {model_path}")

# Prediction function
def predict_captcha(model_path, image_path):
    model = CaptchaModel().to(DEVICE)
    model.load_state_dict(torch.load(model_path))
    model.eval()
    
    try:
        image = Image.open(image_path).convert('L')
    except Exception as e:
        raise ValueError(f"Failed to open test image {image_path}: {str(e)}")
    
    image = transform(image).unsqueeze(0).to(DEVICE)  # Add batch dimension
    
    with torch.no_grad():
        output = model(image)
        pred = torch.argmax(output, dim=2).squeeze(0)
        pred_text = ''.join([idx_to_char[idx.item()] for idx in pred])
    
    return pred_text


def display_menu():
    print("\n--- Choose an Option ---")
    print("1. Train the model")
    print("2. test a single image")
    print("3. Exit")


# Example usage
if __name__ == "__main__":
    while True:
        display_menu()
        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            print("You selected Train the model.")
                # Update with your dataset folder
            dataset_path = "raw_data"  # Path to your folder with 1598 images
            
            # Train the model
            train_model(dataset_path)
            
            # Example prediction (uncomment to test)
            # test_image = "raw_data/Xy9Ab.png"
            # predicted_text = predict_captcha('captcha_model.pth', test_image)
            # print(f"Predicted text: {predicted_text}")


        elif choice == '2':
            print("You selected test a single image.")
            test_image = "test.png"
            predicted_text = predict_captcha('captcha_model.pth', test_image)
            print(f"Predicted text: {predicted_text}")


        elif choice == '3':
            print("Exiting the program.")
            break
        else:
            print("Invalid choice. Please try again.")
    
