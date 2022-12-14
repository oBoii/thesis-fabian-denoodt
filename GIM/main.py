# import importlib

import torch
import time
import numpy as np
import random
import gc
from options import OPTIONS

# own modules
from utils import logger
from arg_parser import arg_parser
from models import load_audio_model
from data import get_dataloader
from validation import val_by_latent_speakers
from validation import val_by_InfoNCELoss

# importlib.reload(logger)
# importlib.reload(arg_parser)
# importlib.reload(load_audio_model)
# importlib.reload(get_dataloader)
# importlib.reload(val_by_latent_speakers)
# importlib.reload(val_by_InfoNCELoss)


def train(opt, model):
    total_step = len(train_loader)

    # how often to output training values
    print_idx = 100
    # how often to validate training process by plotting latent representations of various speakers
    latent_val_idx = 1000

    starttime = time.time()

    for epoch in range(opt["start_epoch"], opt["num_epochs"] + opt["start_epoch"]):

        loss_epoch = [0 for _ in range(opt["model_splits"])]

        # each item of tuple is returned x batch size
        for step, (audio, filename, _, start_idx) in enumerate(train_loader):
            # audio is window of size (64 * 441) starting at random time point

            # full audio sound, but its a multiple of 441 (so small part is gone)
            # print(audio.shape) # eg: [2, 1, 20480] # 2 comes from batch size

            if(opt["dont_train"]):
                if step == 400:  # todo: remove
                    break

            # validate training progress by plotting latent representation of various speakers
            # TODO
            # if step % latent_val_idx == 0:
            #     val_by_latent_speakers.val_by_latent_speakers(
            #         opt, train_dataset, model, epoch, step
            #     )

            if step % print_idx == 0:
                print(
                    "Epoch [{}/{}], Step [{}/{}], Time (s): {:.1f}".format(
                        epoch + 1,
                        opt["num_epochs"] + opt["start_epoch"],
                        step,
                        total_step,
                        time.time() - starttime,
                    )
                )

            starttime = time.time()

            model_input = audio.to(opt["device"])
            # print(audio.shape) # eg: [2, 1, 20480]

            # calls full_model.py > forward
            # Loss is based on 2 audio samples (batch size = 2)
            loss = model(model_input, filename,
                         start_idx, n=opt["train_layer"])

            # average over the losses from different GPUs
            loss = torch.mean(loss, 0)
            # print(loss) bv tensor([2.3979, 2.3967, 2.3920, 2.3834, 2.3853, 2.3862], device='cuda:0',

            model.zero_grad()
            overall_loss = sum(loss)
            overall_loss.backward()
            optimizer.step()

            for idx, cur_losses in enumerate(loss):
                print_loss = cur_losses.item()
                loss_epoch[idx] += print_loss

                if step % print_idx == 0:
                    print("\t \t Loss: \t \t {:.4f}".format(print_loss))

        logs.append_train_loss([x / total_step for x in loss_epoch])

        # validate by testing the CPC performance on the validation set
        if opt["validate"]:
            validation_loss = val_by_InfoNCELoss.val_by_InfoNCELoss(
                opt, model, test_loader)
            logs.append_val_loss(validation_loss)

        if(epoch % opt['log_every_x_epochs'] == 0):
            logs.create_log(model, epoch=epoch, optimizer=optimizer)


if __name__ == "__main__":
    # added myself
    torch.cuda.empty_cache()
    gc.collect()

    opt = OPTIONS

    arg_parser.create_log_path(opt)

    # set random seeds
    torch.manual_seed(opt["seed"])
    torch.cuda.manual_seed(opt["seed"])
    np.random.seed(opt["seed"])
    random.seed(opt["seed"])

    # load model
    model, optimizer = load_audio_model.load_model_and_optimizer(opt)
    
    # initialize logger
    logs = logger.Logger(opt)

    # get datasets and dataloaders
    # train_loader, train_dataset, test_loader, test_dataset = get_dataloader.get_libri_dataloaders(
    train_loader, train_dataset, test_loader, test_dataset = get_dataloader.get_de_boer_sounds_data_loaders(
        opt
    )

    try:
        # Train the model
        train(opt, model)

    except KeyboardInterrupt:
        print("Training got interrupted, saving log-files now.")

    logs.create_log(model)
