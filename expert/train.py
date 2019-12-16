import os
import time
from datetime import datetime
import numpy as np
import torch
from torch.utils.data import DataLoader, SubsetRandomSampler
import torch.optim as optim
import torch.nn as nn
from .util.tboard import TBoard
from .model import ExpertModel
import torch.optim as optim

def train(dataset, config, use_tb=False):
    start_time = time.time()
    if use_tb:
        results_dir = Path(results_dir)
        results_dir = results_dir / str(datetime.fromtimestamp(time.time()))
        os.mkdir(results_dir)
        tb = TBoard(results_dir=results_dir)

    sample_count = len(dataset)

    split = sample_count // 5
    indices = list(range(sample_count))

    valid_idx = np.random.choice(
        indices,
        size=split,
        replace=False)

    train_idx = list(set(indices) - set(valid_idx))
    dataset_sizes = {'train': len(train_idx), 'val': len(valid_idx)}

    train_sampler = SubsetRandomSampler(train_idx)
    valid_sampler = SubsetRandomSampler(valid_idx)

    dataloaders = {
        loader: DataLoader(
            dataset,
            batch_size=config.batch_size,
            num_workers=config.num_workers,
            sampler=sampler,
            drop_last=True
            )
        for (loader, sampler) in [('train', train_sampler), ('val', valid_sampler)]}

    print("Training samples: %s" % len(train_sampler))
    print("Validation samples: %s" % len(valid_sampler))
    print("Samples: %s, %s" % (sample_count, sample_count == len(train_sampler) + len(valid_sampler)))


    # Instantiate Model
    model = ExpertModel(3, 5).to(config.device)
    # print(model)

    # Fit data to model
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters())

    iterations = 0
    start = time.time()
    best_loss = 1000.0
    scheduler = optim.lr_scheduler.CyclicLR(optimizer, base_lr=0.0001, max_lr=0.001)
    
    for epoch in range(config.epochs):
        epoch_time = time.time()
        print('\nEpoch {}/{}'.format(epoch+1, config.epochs))
        print('-' * 10)

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            print(f"Starting {phase} phase")
            if phase == 'train':
                model.train()
            else:
                model.eval()

            running_loss = running_acc = total = 0.0

            # Iterate over data
            for batch_idx, batch in enumerate(dataloaders[phase]):
                train_time = time.time()
                images = batch['image'].to(config.device)
                labels = batch['label'].to(config.device)

                optimizer.zero_grad()

                iterations += 1

                # forward pass
                # track history if only in train
                with torch.set_grad_enabled(phase == 'train'):
                    output = model(images)

                    _, predicted = torch.max(output.data, 1)
                    loss = criterion(output, labels)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                running_loss += loss.item()*output.shape[0]
                running_acc += (predicted == labels).sum().item()
                total += output.size(0)

                if batch_idx % 150 == 0 and phase == 'train':
                    print(f"[{batch_idx}/{len(dataloaders[phase])}] loss: {running_loss/total:.3f}\t acc: {running_acc/total:.3f}")

                scheduler.step()  # step learning rate scheduler
                
            running_loss = running_loss/dataset_sizes[phase]
            running_acc = running_acc/dataset_sizes[phase]
                        
            print(f"{phase.capitalize()}: Loss: {running_loss:.3f}\t Acc: {running_acc:.3f}")
            if (phase == 'val'):
                if running_loss < best_loss:
                    print("New best loss! Saving model...")
                    torch.save(model.state_dict(), "expert_state_dict")
                    best_loss = running_loss

    print(f"finished in {time.time() - start_time}")
    print("Saving finished state_dict...")


    

