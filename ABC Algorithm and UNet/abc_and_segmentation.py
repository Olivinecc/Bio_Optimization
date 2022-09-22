# -*- coding: utf-8 -*-
"""ABC_and_segmentation.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Osqm9ZRz4TFTPFL9QpZfMA3JARB-77Pu
"""

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import tensorflow_datasets as tfds
import matplotlib.pyplot as plt
import numpy as np
import random
import pandas as pd

dataset, info = tfds.load('oxford_iiit_pet:3.*.*', with_info=True)

def resize(input_image, input_mask):
   input_image = tf.image.resize(input_image, (128, 128), method="nearest")
   input_mask = tf.image.resize(input_mask, (128, 128), method="nearest")
   return input_image, input_mask

def augment(input_image, input_mask):
   if tf.random.uniform(()) > 0.5:
       # Random flipping of the image and mask
       input_image = tf.image.flip_left_right(input_image)
       input_mask = tf.image.flip_left_right(input_mask)

   return input_image, input_mask

def normalize(input_image, input_mask):
   input_image = tf.cast(input_image, tf.float32) / 255.0
   input_mask -= 1
   return input_image, input_mask

def load_image_train(datapoint):
   input_image = datapoint["image"]
   input_mask = datapoint["segmentation_mask"]
   input_image, input_mask = resize(input_image, input_mask)
   input_image, input_mask = augment(input_image, input_mask)
   input_image, input_mask = normalize(input_image, input_mask)

   return input_image, input_mask

def load_image_test(datapoint):
   input_image = datapoint["image"]
   input_mask = datapoint["segmentation_mask"]
   input_image, input_mask = resize(input_image, input_mask)
   input_image, input_mask = normalize(input_image, input_mask)

   return input_image, input_mask

def double_conv_block(x, n_filters):

   # Conv2D then ReLU activation
   x = layers.Conv2D(n_filters, 3, padding = "same", activation = "relu", kernel_initializer = "he_normal")(x)
   # Conv2D then ReLU activation
   x = layers.Conv2D(n_filters, 3, padding = "same", activation = "relu", kernel_initializer = "he_normal")(x)

   return x


def downsample_block(x, n_filters, POOLING_TYPE, DROPOUT_RATE):
  f = double_conv_block(x, n_filters)
  
  if POOLING_TYPE == 'MP':
    p = layers.AveragePooling2D(2)(f)

  elif POOLING_TYPE == 'AP':
    p = layers.AveragePooling2D(2)(f)
  g = layers.Dropout(DROPOUT_RATE)(p)

  return f,g


def upsample_block(x, conv_features, n_filters, DROPOUT_RATE):
   # upsample
   x = layers.Conv2DTranspose(n_filters, 3, 2, padding="same")(x)
   # concatenate
   x = layers.concatenate([x, conv_features])
   # dropout
   x = layers.Dropout(DROPOUT_RATE)(x)
   # Conv2D twice with ReLU activation
   x = double_conv_block(x, n_filters)

   return x

def training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE):
  unet_model = build_unet_model()
  unet_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate = LEARNING_RATE),
                    loss="sparse_categorical_crossentropy",
                    metrics="accuracy")
  
  TRAIN_LENGTH = info.splits["train"].num_examples
  STEPS_PER_EPOCH = TRAIN_LENGTH // BATCH_SIZE

  VAL_SUBSPLITS = 5
  TEST_LENTH = info.splits["test"].num_examples
  VALIDATION_STEPS = TEST_LENTH // BATCH_SIZE // VAL_SUBSPLITS

  model_history = unet_model.fit(train_batches,
                                epochs=EPOCHS,
                                steps_per_epoch=STEPS_PER_EPOCH,
                                validation_steps=VALIDATION_STEPS,
                                validation_data=test_batches)
  return model_history

def build_unet_model(): # inputs
   inputs = layers.Input(shape=(128,128,3))

   # encoder: contracting path - downsample
   # 1 - downsample
   f1, p1 = downsample_block(inputs, 64, POOLING_TYPE, DROPOUT_RATE)
   # 2 - downsample
   f2, p2 = downsample_block(p1, 128, POOLING_TYPE, DROPOUT_RATE)
   # 3 - downsample
   f3, p3 = downsample_block(p2, 256, POOLING_TYPE, DROPOUT_RATE)
   # 4 - downsample
   f4, p4 = downsample_block(p3, 512, POOLING_TYPE, DROPOUT_RATE)

   # 5 - bottleneck
   bottleneck = double_conv_block(p4, 1)

   # decoder: expanding path - upsample
   # 6 - upsample
   u6 = upsample_block(bottleneck, f4, 512, DROPOUT_RATE)
   # 7 - upsample
   u7 = upsample_block(u6, f3, 256, DROPOUT_RATE)
   # 8 - upsample
   u8 = upsample_block(u7, f2, 128, DROPOUT_RATE)
   # 9 - upsample
   u9 = upsample_block(u8, f1, 64, DROPOUT_RATE)

   # outputs
   outputs = layers.Conv2D(3, 1, padding="same", activation = "softmax")(u9)

   # unet model with Keras Functional API
   unet_model = tf.keras.Model(inputs, outputs, name="U-Net")

   return unet_model

LEARNING_RATE = .001
EPOCHS = 2
BATCH_SIZE = 64
POOLING_TYPE = 'MP' 
DROPOUT_RATE = .3

train_dataset = dataset["train"].map(load_image_train, num_parallel_calls=tf.data.AUTOTUNE)
test_dataset = dataset["test"].map(load_image_test, num_parallel_calls=tf.data.AUTOTUNE)
BUFFER_SIZE = 1000
train_batches = train_dataset.cache().shuffle(BUFFER_SIZE).batch(BATCH_SIZE).repeat()
train_batches = train_batches.prefetch(buffer_size=tf.data.experimental.AUTOTUNE)
validation_batches = test_dataset.take(3000).batch(BATCH_SIZE)
test_batches = test_dataset.skip(3000).take(669).batch(BATCH_SIZE)

def display(display_list):
 plt.figure(figsize=(15, 15))
 title = ["Input Image", "True Mask", "Predicted Mask"]
 for i in range(len(display_list)):
   plt.subplot(1, len(display_list), i+1)
   plt.title(title[i])
   plt.imshow(tf.keras.utils.array_to_img(display_list[i]))
   plt.axis("off")
 plt.show()
sample_batch = next(iter(train_batches))
random_index = np.random.choice(sample_batch[0].shape[0])
sample_image, sample_mask = sample_batch[0][random_index], sample_batch[1][random_index]
display([sample_image, sample_mask])

dim = 5
gy_size = 5
gc_size = 3
max_gen = 5

limit = round(0.2 * dim * gy_size)

lr_min = 0.001
lr_max = 0.1

epochs_min = 1
epochs_max = 11

batchsize_data = [32,64,128,256]

poolingtype = ['MP', 'AP']

dr_min = 0.001
dr_max = 0.1

L = np.zeros(gy_size)
generation = 1

LearningRate = []
Epochs = []
DropoutRate = []
BatchSize = []
PoolingType = []

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []


for i in range(gy_size):
  LearningRate.append((lr_max-lr_min)*random.random())
  Epochs.append(round((epochs_max-epochs_min)*random.random()))
  DropoutRate.append((dr_max-dr_min)*random.random())
  BatchSize.append(int(np.array(random.sample(batchsize_data,1))))
  PoolingType.append("".join(random.sample(poolingtype,1)))

LearningRate_ori = LearningRate
Epochs_ori = Epochs
DropoutRate_ori = DropoutRate
BatchSize_ori = BatchSize
PoolingType_ori = PoolingType

accuracy = []
for i in range(gy_size):
  LEARNING_RATE = LearningRate[i]
  EPOCHS = Epochs[i]
  DROPOUT_RATE = DropoutRate[i]
  BATCH_SIZE = BatchSize[i]
  POOLING_TYPE = PoolingType[i]
  model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)
  # print(model_history.history)
  if model_history.history:
    temp = model_history.history['accuracy'][-1]
  else:
    temp = 1
  accuracy.append(temp)

maxacc = max(accuracy)
idx_max = int(np.argwhere(np.array(accuracy) == max(accuracy))[0])
accuracy_ori = accuracy

accuracy_ori = accuracy
accuracy_ori

L = np.zeros(gy_size)
generation = 1

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []

LearningRate = LearningRate_ori
Epochs = Epochs_ori
DropoutRate = DropoutRate_ori
BatchSize = BatchSize_ori
PoolingType = PoolingType_ori
accuracy = accuracy_ori

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []

L = np.zeros(gy_size)
generation = 1
max_gen = 3

max_gen = 3

for gen in range(max_gen):

  # Employed bee stage
  for i in range(gy_size):
    k = random.sample(range(gy_size),1)[0]
    while k==i:
        k = random.sample(range(gy_size),1)[0]
        break

    fai = random.random() * 2 - 1
    new_LearningRate =  LearningRate[i] + fai * (LearningRate[i] - LearningRate[k])
    new_Epochs =  round(Epochs[i] + fai * (Epochs[i] - Epochs[k]))
    new_DropoutRate =  DropoutRate[i] + fai * (DropoutRate[i] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[i]
    POOLING_TYPE = PoolingType[i]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)
    
    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1  

    if new_accuracy > accuracy[i]:
      LearningRate[i] = new_LearningRate
      Epochs[i] = new_Epochs
      DropoutRate[i] = new_DropoutRate
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      accuracy[i] = new_accuracy
    else:
      L[i] = L[i] + 1

  # Calculating the cumulative probability
  meanvalue = np.mean(accuracy)
  F = np.zeros(gy_size)
  for i in range(gy_size):
    F[i] = np.exp(-accuracy[i]/meanvalue)

  P = np.cumsum(F/sum(F))

  # onlooker bee stage
  for i in range(gc_size):
    r = random.random()
    for m in range(gy_size):
      if r <= P[m]:
        j = np.argwhere(P == P[m])[0][0]

    k = random.sample(range(gy_size),1)[0]
    while k == j:
      k = random.sample(range(gy_size),1)[0]
      break

    fai = random.random() * 2 - 1

    new_LearningRate =  LearningRate[j] + fai * (LearningRate[j] - LearningRate[k])
    new_Epochs =  round(Epochs[j] + fai * (Epochs[j] - Epochs[k]))
    new_DropoutRate =  DropoutRate[j] + fai * (DropoutRate[j] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[j]
    POOLING_TYPE = PoolingType[j]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1

    if new_accuracy > accuracy[j]:
      LearningRate[j] = new_LearningRate
      Epochs[j] = new_Epochs
      DropoutRate[j] = new_DropoutRate
      BatchSize[j] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[j] = "".join(random.sample(poolingtype,1))
      accuracy[j] = new_accuracy
    else:
      L[j] = L[j] + 1

  # scout bees stage
  for i in range(gy_size):
    if L[i] >= limit:
      rand = np.zeros(5)
      for j in range(5):
        rand[j] = random.random()
      LearningRate[i] = (lr_max - lr_min) * rand[0]
      Epochs[i] = round((epochs_max - epochs_min) * rand[1])
      DropoutRate[i] = (dr_max - dr_min) * rand[2]
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      L[i] = 0

      LEARNING_RATE = LearningRate[i]
      EPOCHS = Epochs[i]
      DROPOUT_RATE = DropoutRate[i]
      BATCH_SIZE = BatchSize[i]
      POOLING_TYPE = PoolingType[i]
      model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

      if model_history:
        new_accuracy = model_history.history['accuracy'][-1]
      else:
        new_accuracy = 1 

      accuracy[i] = new_accuracy
  # Completing a generation of updates
  for i in range(gy_size):
    if accuracy[i] > maxacc:
      best_LearningRate = LearningRate[i]
      best_Epochs = Epochs[i]
      best_DropoutRate = DropoutRate[i]
      best_BatchSize = BatchSize[i]
      best_PoolingType = PoolingType[i]
      maxacc = accuracy[i]
      idx_max = i

  record.append([generation, idx_max, maxacc])
  LearningRate_record.append(LearningRate)
  Epochs_record.append(Epochs)
  DropoutRate_record.append(DropoutRate)
  BatchSize_record.append(BatchSize)
  PoolingType_record.append(PoolingType)

  generation = generation + 1

#record = np.array(record).reshape(-1,3)

record_3 = record
LearningRate_record_3 = LearningRate_record
Epochs_record_3 = Epochs_record
DropoutRate_record_3 = DropoutRate_record
BatchSize_record_3 = BatchSize_record
PoolingType_record_3 = PoolingType_record
L_record_3 = L

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []

generation = 1
max_gen = 3

for gen in range(max_gen):

  # Employed bee stage
  for i in range(gy_size):
    k = random.sample(range(gy_size),1)[0]
    while k==i:
        k = random.sample(range(gy_size),1)[0]
        break

    fai = random.random() * 2 - 1
    new_LearningRate =  LearningRate[i] + fai * (LearningRate[i] - LearningRate[k])
    new_Epochs =  round(Epochs[i] + fai * (Epochs[i] - Epochs[k]))
    new_DropoutRate =  DropoutRate[i] + fai * (DropoutRate[i] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[i]
    POOLING_TYPE = PoolingType[i]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)
    
    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1  

    if new_accuracy > accuracy[i]:
      LearningRate[i] = new_LearningRate
      Epochs[i] = new_Epochs
      DropoutRate[i] = new_DropoutRate
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      accuracy[i] = new_accuracy
    else:
      L[i] = L[i] + 1

  # Calculating the cumulative probability
  meanvalue = np.mean(accuracy)
  F = np.zeros(gy_size)
  for i in range(gy_size):
    F[i] = np.exp(-accuracy[i]/meanvalue)

  P = np.cumsum(F/sum(F))

  # onlooker bee stage
  for i in range(gc_size):
    r = random.random()
    for m in range(gy_size):
      if r <= P[m]:
        j = np.argwhere(P == P[m])[0][0]

    k = random.sample(range(gy_size),1)[0]
    while k == j:
      k = random.sample(range(gy_size),1)[0]
      break

    fai = random.random() * 2 - 1

    new_LearningRate =  LearningRate[j] + fai * (LearningRate[j] - LearningRate[k])
    new_Epochs =  round(Epochs[j] + fai * (Epochs[j] - Epochs[k]))
    new_DropoutRate =  DropoutRate[j] + fai * (DropoutRate[j] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[j]
    POOLING_TYPE = PoolingType[j]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1

    if new_accuracy > accuracy[j]:
      LearningRate[j] = new_LearningRate
      Epochs[j] = new_Epochs
      DropoutRate[j] = new_DropoutRate
      BatchSize[j] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[j] = "".join(random.sample(poolingtype,1))
      accuracy[j] = new_accuracy
    else:
      L[j] = L[j] + 1

  # scout bees stage
  for i in range(gy_size):
    if L[i] >= limit:
      rand = np.zeros(5)
      for j in range(5):
        rand[j] = random.random()
      LearningRate[i] = (lr_max - lr_min) * rand[0]
      Epochs[i] = round((epochs_max - epochs_min) * rand[1])
      DropoutRate[i] = (dr_max - dr_min) * rand[2]
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      L[i] = 0

      LEARNING_RATE = LearningRate[i]
      EPOCHS = Epochs[i]
      DROPOUT_RATE = DropoutRate[i]
      BATCH_SIZE = BatchSize[i]
      POOLING_TYPE = PoolingType[i]
      model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

      if model_history:
        new_accuracy = model_history.history['accuracy'][-1]
      else:
        new_accuracy = 1 

      accuracy[i] = new_accuracy
  # Completing a generation of updates
  for i in range(gy_size):
    if accuracy[i] > maxacc:
      best_LearningRate = LearningRate[i]
      best_Epochs = Epochs[i]
      best_DropoutRate = DropoutRate[i]
      best_BatchSize = BatchSize[i]
      best_PoolingType = PoolingType[i]
      maxacc = accuracy[i]
      idx_max = i

  record.append([generation, idx_max, maxacc])
  LearningRate_record.append(LearningRate)
  Epochs_record.append(Epochs)
  DropoutRate_record.append(DropoutRate)
  BatchSize_record.append(BatchSize)
  PoolingType_record.append(PoolingType)

  generation = generation + 1

#record = np.array(record).reshape(-1,3)

record_6 = record
LearningRate_record_6 = LearningRate_record
Epochs_record_6 = Epochs_record
DropoutRate_record_6 = DropoutRate_record
BatchSize_record_6 = BatchSize_record
PoolingType_record_6 = PoolingType_record
L_record_6 = L

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []

generation = 1
max_gen = 4

for gen in range(max_gen):

  # Employed bee stage
  for i in range(gy_size):
    k = random.sample(range(gy_size),1)[0]
    while k==i:
        k = random.sample(range(gy_size),1)[0]
        break

    fai = random.random() * 2 - 1
    new_LearningRate =  LearningRate[i] + fai * (LearningRate[i] - LearningRate[k])
    new_Epochs =  round(Epochs[i] + fai * (Epochs[i] - Epochs[k]))
    new_DropoutRate =  DropoutRate[i] + fai * (DropoutRate[i] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[i]
    POOLING_TYPE = PoolingType[i]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)
    
    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1  

    if new_accuracy > accuracy[i]:
      LearningRate[i] = new_LearningRate
      Epochs[i] = new_Epochs
      DropoutRate[i] = new_DropoutRate
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      accuracy[i] = new_accuracy
    else:
      L[i] = L[i] + 1

  # Calculating the cumulative probability
  meanvalue = np.mean(accuracy)
  F = np.zeros(gy_size)
  for i in range(gy_size):
    F[i] = np.exp(-accuracy[i]/meanvalue)

  P = np.cumsum(F/sum(F))

  # onlooker bee stage
  for i in range(gc_size):
    r = random.random()
    for m in range(gy_size):
      if r <= P[m]:
        j = np.argwhere(P == P[m])[0][0]

    k = random.sample(range(gy_size),1)[0]
    while k == j:
      k = random.sample(range(gy_size),1)[0]
      break

    fai = random.random() * 2 - 1

    new_LearningRate =  LearningRate[j] + fai * (LearningRate[j] - LearningRate[k])
    new_Epochs =  round(Epochs[j] + fai * (Epochs[j] - Epochs[k]))
    new_DropoutRate =  DropoutRate[j] + fai * (DropoutRate[j] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[j]
    POOLING_TYPE = PoolingType[j]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1

    if new_accuracy > accuracy[j]:
      LearningRate[j] = new_LearningRate
      Epochs[j] = new_Epochs
      DropoutRate[j] = new_DropoutRate
      BatchSize[j] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[j] = "".join(random.sample(poolingtype,1))
      accuracy[j] = new_accuracy
    else:
      L[j] = L[j] + 1

  # scout bees stage
  for i in range(gy_size):
    if L[i] >= limit:
      rand = np.zeros(5)
      for j in range(5):
        rand[j] = random.random()
      LearningRate[i] = (lr_max - lr_min) * rand[0]
      Epochs[i] = round((epochs_max - epochs_min) * rand[1])
      DropoutRate[i] = (dr_max - dr_min) * rand[2]
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      L[i] = 0

      LEARNING_RATE = LearningRate[i]
      EPOCHS = Epochs[i]
      DROPOUT_RATE = DropoutRate[i]
      BATCH_SIZE = BatchSize[i]
      POOLING_TYPE = PoolingType[i]
      model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

      if model_history:
        new_accuracy = model_history.history['accuracy'][-1]
      else:
        new_accuracy = 1 

      accuracy[i] = new_accuracy
  # Completing a generation of updates
  for i in range(gy_size):
    if accuracy[i] > maxacc:
      best_LearningRate = LearningRate[i]
      best_Epochs = Epochs[i]
      best_DropoutRate = DropoutRate[i]
      best_BatchSize = BatchSize[i]
      best_PoolingType = PoolingType[i]
      maxacc = accuracy[i]
      idx_max = i

  record.append([generation, idx_max, maxacc])
  LearningRate_record.append(LearningRate)
  Epochs_record.append(Epochs)
  DropoutRate_record.append(DropoutRate)
  BatchSize_record.append(BatchSize)
  PoolingType_record.append(PoolingType)

  generation = generation + 1

#record = np.array(record).reshape(-1,3)

record_10 = record
LearningRate_record_10 = LearningRate_record
Epochs_record_10 = Epochs_record
DropoutRate_record_10 = DropoutRate_record
BatchSize_record_10 = BatchSize_record
PoolingType_record_10 = PoolingType_record
L_record_10 = L

record = []
LearningRate_record = []
Epochs_record = []
DropoutRate_record = []
BatchSize_record = []
PoolingType_record = []

generation = 1
max_gen = 5

for gen in range(max_gen):

  # Employed bee stage
  for i in range(gy_size):
    k = random.sample(range(gy_size),1)[0]
    while k==i:
        k = random.sample(range(gy_size),1)[0]
        break

    fai = random.random() * 2 - 1
    new_LearningRate =  LearningRate[i] + fai * (LearningRate[i] - LearningRate[k])
    new_Epochs =  round(Epochs[i] + fai * (Epochs[i] - Epochs[k]))
    new_DropoutRate =  DropoutRate[i] + fai * (DropoutRate[i] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[i]
    POOLING_TYPE = PoolingType[i]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)
    
    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1  

    if new_accuracy > accuracy[i]:
      LearningRate[i] = new_LearningRate
      Epochs[i] = new_Epochs
      DropoutRate[i] = new_DropoutRate
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      accuracy[i] = new_accuracy
    else:
      L[i] = L[i] + 1

  # Calculating the cumulative probability
  meanvalue = np.mean(accuracy)
  F = np.zeros(gy_size)
  for i in range(gy_size):
    F[i] = np.exp(-accuracy[i]/meanvalue)

  P = np.cumsum(F/sum(F))

  # onlooker bee stage
  for i in range(gc_size):
    r = random.random()
    for m in range(gy_size):
      if r <= P[m]:
        j = np.argwhere(P == P[m])[0][0]

    k = random.sample(range(gy_size),1)[0]
    while k == j:
      k = random.sample(range(gy_size),1)[0]
      break

    fai = random.random() * 2 - 1

    new_LearningRate =  LearningRate[j] + fai * (LearningRate[j] - LearningRate[k])
    new_Epochs =  round(Epochs[j] + fai * (Epochs[j] - Epochs[k]))
    new_DropoutRate =  DropoutRate[j] + fai * (DropoutRate[j] - DropoutRate[k])

    new_LearningRate = min(lr_max,new_LearningRate)
    new_LearningRate = max(lr_min,new_LearningRate)

    new_Epochs = min(epochs_max,new_Epochs)
    new_Epochs = max(epochs_min,new_Epochs)

    new_DropoutRate = min(dr_max,new_DropoutRate)
    new_DropoutRate = max(dr_min,new_DropoutRate)

    LEARNING_RATE = new_LearningRate
    EPOCHS = new_Epochs
    DROPOUT_RATE = new_DropoutRate
    BATCH_SIZE = BatchSize[j]
    POOLING_TYPE = PoolingType[j]

    model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

    if model_history:
      new_accuracy = model_history.history['accuracy'][-1]
    else:
      new_accuracy = 1

    if new_accuracy > accuracy[j]:
      LearningRate[j] = new_LearningRate
      Epochs[j] = new_Epochs
      DropoutRate[j] = new_DropoutRate
      BatchSize[j] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[j] = "".join(random.sample(poolingtype,1))
      accuracy[j] = new_accuracy
    else:
      L[j] = L[j] + 1

  # scout bees stage
  for i in range(gy_size):
    if L[i] >= limit:
      rand = np.zeros(5)
      for j in range(5):
        rand[j] = random.random()
      LearningRate[i] = (lr_max - lr_min) * rand[0]
      Epochs[i] = round((epochs_max - epochs_min) * rand[1])
      DropoutRate[i] = (dr_max - dr_min) * rand[2]
      BatchSize[i] = int(np.array(random.sample(batchsize_data,1)))
      PoolingType[i] = "".join(random.sample(poolingtype,1))
      L[i] = 0

      LEARNING_RATE = LearningRate[i]
      EPOCHS = Epochs[i]
      DROPOUT_RATE = DropoutRate[i]
      BATCH_SIZE = BatchSize[i]
      POOLING_TYPE = PoolingType[i]
      model_history = training_the_model(info, train_batches, test_batches, LEARNING_RATE, BATCH_SIZE, EPOCHS, POOLING_TYPE, DROPOUT_RATE)

      if model_history:
        new_accuracy = model_history.history['accuracy'][-1]
      else:
        new_accuracy = 1 

      accuracy[i] = new_accuracy
  # Completing a generation of updates
  for i in range(gy_size):
    if accuracy[i] > maxacc:
      best_LearningRate = LearningRate[i]
      best_Epochs = Epochs[i]
      best_DropoutRate = DropoutRate[i]
      best_BatchSize = BatchSize[i]
      best_PoolingType = PoolingType[i]
      maxacc = accuracy[i]
      idx_max = i

  record.append([generation, idx_max, maxacc])
  LearningRate_record.append(LearningRate)
  Epochs_record.append(Epochs)
  DropoutRate_record.append(DropoutRate)
  BatchSize_record.append(BatchSize)
  PoolingType_record.append(PoolingType)

  generation = generation + 1

#record = np.array(record).reshape(-1,3)

record_15 = record
LearningRate_record_15 = LearningRate_record
Epochs_record_15 = Epochs_record
DropoutRate_record_15 = DropoutRate_record
BatchSize_record_15 = BatchSize_record
PoolingType_record_15 = PoolingType_record
L_record_15 = L

record_15

idx = record_15[max_gen-1][1]

LEARNING_RATE = LearningRate_record_15[max_gen-1][idx]
EPOCHS = Epochs_record_15[max_gen-1][idx]
DROPOUT_RATE = DropoutRate_record_15[max_gen-1][idx]
BATCH_SIZE = BatchSize_record_15[max_gen-1][idx]
POOLING_TYPE = PoolingType_record_15[max_gen-1][idx]

unet_model = build_unet_model()

unet_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate = LEARNING_RATE),
                  loss="sparse_categorical_crossentropy",
                  metrics="accuracy")

TRAIN_LENGTH = info.splits["train"].num_examples
STEPS_PER_EPOCH = TRAIN_LENGTH // BATCH_SIZE

VAL_SUBSPLITS = 5
TEST_LENTH = info.splits["test"].num_examples
VALIDATION_STEPS = TEST_LENTH // BATCH_SIZE // VAL_SUBSPLITS

model_history = unet_model.fit(train_batches,
                              epochs=EPOCHS,
                              steps_per_epoch=STEPS_PER_EPOCH,
                              validation_steps=VALIDATION_STEPS,
                              validation_data=test_batches)