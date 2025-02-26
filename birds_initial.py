###############################################################################
# Load all necessary libraries for the analysis

import cv2
import glob
import h5py
import imp
import keras_tuner as kt
import matplotlib.pyplot as plt
import numpy as np
import os
import random
import shutil
import tensorflow as tf
import time

import skimage.measure
import imghdr
import skimage as sk
from skimage import util, io, transform

import keras
from keras.preprocessing.image import ImageDataGenerator
from keras.callbacks import LearningRateScheduler, ModelCheckpoint
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D
from keras.optimizers import SGD

from collections import Counter, deque
from moviepy.editor import *
from moviepy.video.io.VideoFileClip import VideoFileClip
from mpl_toolkits.axes_grid1 import ImageGrid
from scipy import ndarray
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
from difPy import dif

###############################################################################
# Identify all directories for the analysis

# Parent directory path.  This directory is the parent directory for the entire project and likely the working directory 
os.chdir('D:/School_Files/AI_801/Project/final_project_git')

# Directory to master image file
image_dir = './data/' 

# Directory to train/test split data
#split_path = './simpsons_split'

# Directory to augmented image file
#aug_path = './simpsons_augmented'

# Directory to weights path
best_weights_path = "./best_weights_6conv_birds.hdf5"

# Directory to weights path after tuning
#tuned_best_weights_path = "./tuned_best_weights_6conv_simpsons.hdf5"

map_birds = dict(list(enumerate([os.path.basename(x) for x in glob.glob(image_dir + '/train/*')])))

##############################################################################
# Exploratiory analytics for the dataset

# Get the min and max number of images from the dataset
species_size = []
for k, char in map_birds.items():
    species_size.append(len(glob.glob(image_dir + '/train/%s/*' % char)))

print('Minimum number of images is ' + str(min(species_size)))
print('Maximimum number of images is ' + str(max(species_size)))

# Test to determine of all images are size (224, 224, 3) as the dataset claims
image_size = []
for k, char in map_birds.items():
    pictures_size = [k for k in glob.glob(image_dir + '/train/%s/*' % char)]

    for pic in pictures_size:
        a = cv2.imread(pic)
        image_size.append(a.shape)
    
print('Total number of images not equal to (224, 224, 3) = ' + str(sum(x != (224, 224, 3) for x in image_size)))

# Identify if duplicate images are present in the dataset
dup_images = []
for k, char in map_birds.items():
    search = dif(image_dir + '/train/%s/' % char)
    dup_images.append(search.result)
    
    
filtered = filter(lambda Total_Dups: dup_images.Size >= 1, dup_images)
print(list(filtered))

##############################################################################
# Identify all fixed variables that will be used in the functions below

pic_size = 128 #The size that each image will be modified to
batch_size = 32 #The batch size the images will be fed through the model
epochs = 50 #The number of epochs that will be run
num_classes = len(map_birds) #The number of classes for the analysis (number of characters)

##############################################################################

def load_pictures(BGR):

    train_pics = []
    train_labels = []
    
    test_pics = []
    test_labels = []
    
    valid_pics = []
    valid_labels = []
    
    for k, char in map_birds.items():
        pictures_train = [k for k in glob.glob(image_dir + '/train/%s/*' % char)]

        for pic in pictures_train:
            a = cv2.imread(pic)
            if BGR:
                a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
            a = cv2.resize(a, (pic_size,pic_size))
            train_pics.append(a)
            train_labels.append(k)
            
        pictures_test = [k for k in glob.glob(image_dir + '/test/%s/*' % char)]
        
        for pic in pictures_test:
            a = cv2.imread(pic)
            if BGR:
                a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
            a = cv2.resize(a, (pic_size,pic_size))
            test_pics.append(a)
            test_labels.append(k)
            
        pictures_valid = [k for k in glob.glob(image_dir + '/valid/%s/*' % char)]
        
        for pic in pictures_valid:
            a = cv2.imread(pic)
            if BGR:
                a = cv2.cvtColor(a, cv2.COLOR_BGR2RGB)
            a = cv2.resize(a, (pic_size,pic_size))
            valid_pics.append(a)
            valid_labels.append(k)

    return np.array(train_pics), np.array(train_labels), np.array(test_pics), np.array(test_labels), np.array(valid_pics), np.array(valid_labels) 

def get_dataset(save=False, load=False, BGR=False):
    """
    Create the actual dataset split into train and test, pictures content is as float32 and
    normalized (/255.). The dataset could be saved or loaded from h5 files.
    :param save: saving or not the created dataset
    :param load: loading or not the dataset
    :param BGR: boolean to use true color for the picture (RGB instead of BGR for plt)
    :return: X_train, X_test, y_train, y_test (numpy arrays)
    """
    if load:
        h5f = h5py.File('dataset.h5','r')
        X_train = h5f['X_train'][:]
        X_val = h5f['X_val'][:]
        X_test = h5f['X_test'][:]
        h5f.close()    

        h5f = h5py.File('labels.h5','r')
        y_train = h5f['y_train'][:]
        y_val = h5f['y_val'][:]
        y_test = h5f['y_test'][:]
        h5f.close()    
    else:
        X_train, y_train, X_test, y_test, X_val, y_val = load_pictures(BGR)
        y_train = keras.utils.to_categorical(y_train, num_classes)
        y_test = keras.utils.to_categorical(y_test, num_classes)
        y_val = keras.utils.to_categorical(y_val, num_classes)
        
        if save:
            h5f = h5py.File('dataset.h5', 'w')
            h5f.create_dataset('X_train', data=X_train)
            h5f.create_dataset('X_val', data=X_val)
            h5f.create_dataset('X_test', data=X_test)
            h5f.close()

            h5f = h5py.File('labels.h5', 'w')
            h5f.create_dataset('y_train', data=y_train)
            h5f.create_dataset('y_val', data=y_val)
            h5f.create_dataset('y_test', data=y_test)
            h5f.close()
            
    X_train = X_train.astype('float32') / 255.
    X_val = X_val.astype('float32') / 255.
    X_test = X_test.astype('float32') / 255.
    print("Train", X_train.shape, y_train.shape)
    print("Val", X_val.shape, y_val.shape)
    print("Test", X_test.shape, y_test.shape)
    if not load:
        dist = {k:tuple(d[k] for d in [dict(Counter(np.where(y_train==1)[1])), dict(Counter(np.where(y_test==1)[1]))])
                for k in range(num_classes)}
        print('\n'.join(["%s : %d train pictures & %d val pictures" % (map_birds[k], v[0], v[1]) 
            for k,v in sorted(dist.items(), key=lambda x:x[1][0], reverse=True)]))
    return X_train, X_val, X_test, y_train, y_val, y_test

def create_model_six_conv(input_shape):
    """
    CNN Keras model with 6 convolutions.
    :param input_shape: input shape, generally X_train.shape[1:]
    :return: Keras model, RMS prop optimizer
    """
    model = Sequential()
    model.add(Conv2D(32, (3, 3), padding='same', input_shape=input_shape))
    model.add(Activation('relu'))
    model.add(Conv2D(32, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))
    
    model.add(Conv2D(64, (3, 3), padding='same'))
    model.add(Activation('relu'))
    model.add(Conv2D(64, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))

    model.add(Conv2D(256, (3, 3), padding='same')) 
    model.add(Activation('relu'))
    model.add(Conv2D(256, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))

    model.add(Flatten())
    model.add(Dense(1024))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(num_classes, activation='softmax'))
    opt = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
    model.compile(loss='categorical_crossentropy',
          optimizer=opt,
          metrics=['accuracy'])  
    return model, opt

def load_model_from_checkpoint(weights_path, input_shape=(pic_size,pic_size,3)):
    model, opt = create_model_six_conv(input_shape)
    model.load_weights(weights_path)
    return model

def lr_schedule(epoch):
    lr = 0.01
    return lr*(0.1**int(epoch/10))

def training(model, X_train, X_val, y_train, y_val, best_weights_path, data_augmentation=True):

    if data_augmentation:
        datagen = ImageDataGenerator(
            featurewise_center=False,  # set input mean to 0 over the dataset
            samplewise_center=False,  # set each sample mean to 0
            featurewise_std_normalization=False,  # divide inputs by std of the dataset
            samplewise_std_normalization=False,  # divide each input by its std
            zca_whitening=False,  # apply ZCA whitening
            rotation_range=10,  # randomly rotate images in the range (degrees, 0 to 180)
            width_shift_range=0.1,  # randomly shift images horizontally (fraction of total width)
            height_shift_range=0.1,  # randomly shift images vertically (fraction of total height)
            horizontal_flip=False,  # randomly flip images
            vertical_flip=True)  # randomly flip images
        # Compute quantities required for feature-wise normalization
        # (std, mean, and principal components if ZCA whitening is applied).
        datagen.fit(X_train)
        filepath = best_weights_path
        checkpoint = ModelCheckpoint(filepath, monitor='val_accuracy', verbose=0, save_best_only=True, mode='max')
        callbacks_list = [LearningRateScheduler(lr_schedule) ,checkpoint]
        history = model.fit(datagen.flow(X_train, y_train,
                            batch_size=batch_size),
                            steps_per_epoch=X_train.shape[0] // batch_size,
                            epochs=epochs,
                            validation_data=(X_val, y_val),
                            callbacks=callbacks_list)        
    else:
        history = model.fit(X_train, y_train,
          batch_size=batch_size,
          epochs=epochs,
          validation_data=(X_val, y_val),
          shuffle=True)
    return model, history

if __name__ == '__main__':
    X_train, X_val, X_test, y_train, y_val, y_test = get_dataset(load=True)
    model, opt = load_model_from_checkpoint(best_weights_path)
    model, history = training(model, X_train, X_val, y_train, y_val, best_weights_path = best_weights_path, data_augmentation=True)


imgplot = plt.imshow(X_test[2])
plt.show()

##############################################################################
#KERAS TUNER

def build_model(hp):
    # create model object
    model = keras.Sequential([
    
    keras.layers.Conv2D(
        filters=hp.Int('conv_1_filter', min_value=32, max_value=128, step=32), 
        kernel_size=(3, 3),
        activation=hp.Choice('conv_1_activation', values = ['relu', 'elu']),
        padding='same', 
        input_shape=(128,128,3)),  
    keras.layers.Conv2D(
        filters=hp.Int('conv_2_filter', min_value=32, max_value=128, step=32), 
        kernel_size=(3, 3),
        activation=hp.Choice('conv_2_activation', values = ['relu', 'elu'])),
    keras.layers.MaxPooling2D(
        pool_size=(2, 2)),
    keras.layers.Dropout(0.2),
    
    keras.layers.Conv2D(
        filters=hp.Int('conv_3_filter', min_value=32, max_value=128, step=32),
        kernel_size=(3, 3),
        activation=hp.Choice('conv_3_activation', values = ['relu', 'elu']),
        padding='same'),  
    keras.layers.Conv2D(
        filters=hp.Int('conv_4_filter', min_value=32, max_value=128, step=32), 
        kernel_size=(3, 3),
        activation=hp.Choice('conv_4_activation', values = ['relu', 'elu'])),
    keras.layers.MaxPooling2D(
        pool_size=(2, 2)),
    keras.layers.Dropout(0.2),
    
    keras.layers.Conv2D(
        filters=hp.Int('conv_5_filter', min_value=128, max_value=512, step=128),
        kernel_size=(3, 3),
        activation=hp.Choice('conv_5_activation', values = ['relu', 'elu']),
        padding='same'),  
    keras.layers.Conv2D(
        filters=hp.Int('conv_6_filter', min_value=128, max_value=512, step=128),
        kernel_size=(3, 3),
        activation=hp.Choice('conv_6_activation', values = ['relu', 'elu'])),
    keras.layers.MaxPooling2D(
        pool_size=(2, 2)),
    keras.layers.Dropout(0.2),
    
    keras.layers.Flatten(),
    keras.layers.Dense(
        units=hp.Int('dense_1_units', min_value=512, max_value=2048, step=512),
        activation=hp.Choice('dense_1_activation', values = ['relu', 'elu'])),
    keras.layers.Dropout(0.5),
    keras.layers.Dense(num_classes, activation='softmax')
    ])
    
    #compilation of model
    model.compile(
        optimizer=keras.optimizers.SGD(
            lr=hp.Choice('learning_rate', values=[1e-2, 1e-3, 1e-4]), 
            decay=1e-6, 
            momentum=0.9, 
            nesterov=True),
        loss='categorical_crossentropy',
        metrics=['accuracy']) 
    
    return model

#creating randomsearch object
tuner = kt.Hyperband(build_model,
                     objective='val_accuracy',
                     max_epochs=10,
                     factor=3,
                     directory='my_dir',
                     project_name='bird_tuner')

stop_early = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5)

tuner.search(X_train,y_train, epochs=50, validation_data=(X_test,y_test), callbacks=[stop_early])

# Get the optimal hyperparameters
best_hps=tuner.get_best_hyperparameters(num_trials=1)[0]

##############################################################################
# New model based on the results from Keras Tuner

def tuned_model_six_conv(input_shape):
    """
    CNN Keras model with 6 convolutions.
    :param input_shape: input shape, generally X_train.shape[1:]
    :return: Keras model, RMS prop optimizer
    """
    model = Sequential()
    model.add(Conv2D(96, (3, 3), padding='same', input_shape=input_shape))
    model.add(Activation('elu'))
    model.add(Conv2D(96, (3, 3)))
    model.add(Activation('elu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))
    
    model.add(Conv2D(96, (3, 3), padding='same'))
    model.add(Activation('relu'))
    model.add(Conv2D(384, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))

    model.add(Conv2D(384, (3, 3), padding='same')) 
    model.add(Activation('elu'))
    model.add(Conv2D(256, (3, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.2))

    model.add(Flatten())
    model.add(Dense(1536))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(num_classes, activation='softmax'))
    opt = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
    model.compile(loss='categorical_crossentropy',
          optimizer=opt,
          metrics=['accuracy'])  
    return model, opt

if __name__ == '__main__':
    X_train, X_val, X_test, y_train, y_val, y_test = get_dataset(save=True)
    model, opt = tuned_model_six_conv(X_train.shape[1:])
    model, history = training(model, X_train, X_val, y_train, y_val, best_weights_path = best_weights_path, data_augmentation=True)
      
##############################################################################
# Ceate image matrix with percentages

F = plt.figure(1, (15,20))
grid = ImageGrid(F, 111, nrows_ncols=(6, 6), axes_pad=0, label_mode="1")

for i in range(36):
    char = map_birds[i]
    image = cv2.imread(np.random.choice([k for k in glob.glob(image_dir + '/train/%s/*' % char) if char in k]))
    img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pic = cv2.resize(image, (pic_size, pic_size)).astype('float32') / 255.
    a = model.predict(pic.reshape(1, pic_size, pic_size, 3))[0]
    actual = char.split('_')[0].title()
    text = sorted(['{:s} : {:.1f}%'.format(map_birds[k].split('_')[0].title(), 100*v) for k,v in enumerate(a)], 
       key=lambda x:float(x.split(':')[1].split('%')[0]), reverse=True)[:3]
    img = cv2.resize(img, (352, 352))
    cv2.rectangle(img, (0,260),(215,352),(255,255,255), -1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, 'Actual : %s' % actual, (10, 280), font, 0.7,(0,0,0),2,cv2.LINE_AA)
    for k, t in enumerate(text):
        cv2.putText(img, t,(10, 300+k*18), font, 0.65,(0,0,0),2,cv2.LINE_AA)
    grid[i].imshow(img)

#EVERYTHING BELOW HERE IS FOR IMAGE AUGMENTATION       
##############################################################################

# Create all image augmentation functions

# Random image rotation between -45 anf 45 deg
def random_rotation(image_array: ndarray):
    # pick a random degree of rotation between 25% on the left and 25% on the right
    random_degree = random.randint(-45, 45)
    return sk.transform.rotate(image_array, random_degree)

# Random noise
def random_noise(image_array: ndarray):
    # add random noise to the image
    return sk.util.random_noise(image_array)

# Flip the image on the y axis (horizontally)
def horizontal_flip(image_array: ndarray):
    # horizontal flip doesn't need skimage, it's easy as flipping the image array of pixels !
    return image_array[:, ::-1]

# Randomly crop 1 to 75 pixels from each side of the image
def crop_image(image_array: ndarray):
    rand_1 = random.randint(10,75)
    rand_2 = random.randint(10,75)
    rand_3 = random.randint(10,75)
    rand_4 = random.randint(10,75)
    return sk.util.crop(image_array, ((rand_1, rand_2), (rand_3, rand_4), (0,0)), copy=False)

# Create a dictionary of the transformations we defined above for use in functions
available_transformations = {'rotate': random_rotation,
                             'noise': random_noise,
                             'horizontal_flip': horizontal_flip,
                             'crop': crop_image
                             }

##############################################################################

x = []
for k, char in map_birds.items():
    x.append(len(glob.glob(image_dir + '/train/%s/*' % char)))
    
min(x)
max(x)

y = []
for k, char in map_birds.items():
    pictures_size = [k for k in glob.glob(image_dir + '/train/%s/*' % char)]

    for pic in pictures_size:
        a = cv2.imread(pic)
        y.append(a.shape)
        
       
##############################################################################

def image_augmentation(train_images = train_images, test_images = test_images):
    # Check if augmented directory exists
    folder_check = os.path.isdir(aug_path)
            
    if not folder_check:
        os.makedirs(aug_path)
        print("created folder : ", aug_path)
    else:
        print(aug_path, "already exists.")
        
        for folder in os.listdir(split_path):
            if folder == 'train':
                aug_images_number = train_images
                split = 'train'
            else:
                aug_images_number = test_images
                split = 'test'       
        
            for k, char in map_characters.items():
                folder_path = os.path.join(aug_path, split, char)             
                num_files_desired = aug_images_number            
                subfolder_check = os.path.isdir(folder_path)
                
                if not subfolder_check:
                    shutil.copytree(os.path.join(image_dir , char), folder_path)
                    print("copied folder : ", folder_path)
                    
                    images = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            
                    num_generated_files = len(os.listdir(os.path.join(image_dir , char)))
                    while num_generated_files <= num_files_desired:
                        # random image from the folder
                        image_path = random.choice(images)
                        # read image as an two dimensional array of pixels
                        image_to_transform = sk.io.imread(image_path)
                        # random num of transformation to apply
                        num_transformations_to_apply = random.randint(1, len(available_transformations))
                    
                        num_transformations = 0
                        transformed_image = None
                        while num_transformations <= num_transformations_to_apply:
                            # random transformation to apply for a single image
                            key = random.choice(list(available_transformations))
                            transformed_image = available_transformations[key](image_to_transform)
                            num_transformations += 1
                    
                            new_file_path = '%s/pic_%s.jpg' % (folder_path, num_generated_files)
                    
                            # write image to the disk
                            io.imsave(new_file_path, transformed_image)
                        num_generated_files += 1    
                        
                elif len(glob.glob(aug_path + '/%s/*' % char)) < aug_images_number:
                    
                    print('adding ', (aug_images_number - len(glob.glob(aug_path + '/%s/*' % char))), ' images to ', folder_path)
                    num_generated_files = len(glob.glob(aug_path + '/%s/*' % char))
                    images = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
                    
                    while num_generated_files <= num_files_desired:
                        # random image from the folder
                        image_path = random.choice(images)
                        # read image as an two dimensional array of pixels
                        image_to_transform = sk.io.imread(image_path)
                        # random num of transformation to apply
                        num_transformations_to_apply = random.randint(1, len(available_transformations))
                    
                        num_transformations = 0
                        transformed_image = None
                        while num_transformations <= num_transformations_to_apply:
                            # random transformation to apply for a single image
                            key = random.choice(list(available_transformations))
                            transformed_image = available_transformations[key](image_to_transform)
                            num_transformations += 1
                    
                            new_file_path = '%s/pic_%s.jpg' % (folder_path, num_generated_files)
                    
                            # write image to the disk
                            io.imsave(new_file_path, transformed_image)
                        num_generated_files += 1
                else:
                    print(folder_path, "already exists.")
                    
                    
                    
#############################################################################

# Function that searches the folder for image files, converts them to a tensor
def create_imgs_matrix(directory, px_size=50):
    global image_files   
    image_files = []
    # create list of all files in directory     
    folder_files = [filename for filename in os.listdir(directory)]  
    
    # create images matrix   
    counter = 0
    for filename in folder_files: 
        # check if the file is accesible and if the file format is an image
        if not os.path.isdir(directory + filename) and imghdr.what(directory + filename):
            # decode the image and create the matrix
            img = cv2.imdecode(np.fromfile(directory + filename, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if type(img) == np.ndarray:
                img = img[...,0:3]
                # resize the image based on the given compression value
                img = cv2.resize(img, dsize=(px_size, px_size), interpolation=cv2.INTER_CUBIC)
                if counter == 0:
                    imgs_matrix = img
                    image_files.append(filename)
                    counter += 1
                else:
                    imgs_matrix = np.concatenate((imgs_matrix, img))
                    image_files.append(filename)
    return imgs_matrix

for k, char in map_birds.items():
        test = [k for k in glob.glob(image_dir + '/train/%s/*' % char)]
        imghdr.what(test, h=None)
        
