import tensorflow as tf
import numpy as np
from import_data import import_data
import os
from datetime import datetime
from collections import OrderedDict

from config import WORKSPACE, LOG_DIR, MODEL_SAVE_DIR, IMAGE_SIZE, NUM_CLASSES, NUM_CHANNELS, CONV1_ACTIV_FUNC, CONV1_STRIDE, CONV1_PADDING, POOL1_FILTER_SIZE, POOL1_STRIDE, POOL1_PADDING, CONV2_ACTIV_FUNC, CONV2_STRIDE, CONV2_PADDING, POOL2_FILTER_SIZE, POOL2_STRIDE, POOL2_PADDING, FC1_ACTIV_FUNC, FC1_NUM_NEURONS, LEARNING_RATE, NUM_ITERS, BATCH_SIZE

print "WORKSPACE:",WORKSPACE

train_data, validation_data, test_data, train_labels, validation_labels, test_labels = import_data()

train_data = np.reshape(train_data, (train_data.shape[0], train_data.shape[1] * train_data.shape[2]))
validation_data = np.reshape(validation_data, (validation_data.shape[0], validation_data.shape[1] * validation_data.shape[2]))
test_data = np.reshape(test_data, (test_data.shape[0], test_data.shape[1] * test_data.shape[2]))

print "Train Data Size", train_data.shape
print "Train Labels Size", train_labels.shape
print "Validation Data Size", validation_data.shape
print "Validation Labels Size", validation_labels.shape
print "Test Data Size", test_data.shape
print "Test Labels Size", test_labels.shape

model_base_name = "model_config_"
log_base_name = "log_config_"

# create a placeholder for input
x = tf.placeholder(tf.float32, [None, IMAGE_SIZE * IMAGE_SIZE])

# to implement cross entropy we need to add a placeholder to input the correct answers
y_ = tf.placeholder(tf.float32, [None, NUM_CLASSES])

# placeholder for keep probability for the dropout layer
keep_prob = tf.placeholder(tf.float32)

# create functions to initialize weights with a slightly positive initial bias to avoid "dead neurons"
def weight_variable(shape, name):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial, name=name)

def bias_variable(shape, name):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial, name=name)

# convolution and pooling
def conv2d(x, W, stride, padding):
    return tf.nn.conv2d(x, W, strides=[1, stride, stride, 1], padding=padding)

def max_pool_2x2(x, ksize, stride, padding):
    return tf.nn.max_pool(x, ksize=[1, ksize[0], ksize[1], 1], strides=[1, stride, stride, 1], padding=padding)

def train_model(iteration, config, config_names):
    with tf.Session() as sess:
        model_name = model_base_name + str(iteration)
        model_dir = MODEL_SAVE_DIR + model_name + '/'
        log_dir = LOG_DIR + log_base_name + str(iteration) + '/'

        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        print "PREPARING TO TRAIN:", model_name
        print "Current configuration is:", config

        # first convolutional layer
        W_conv1 = weight_variable([config[0][0], config[0][1], NUM_CHANNELS, config[2]], 'W_conv1')
        b_conv1 = bias_variable([config[2]], 'b_conv1')
        tf.summary.image('W_conv1', tf.transpose(W_conv1, [3, 0, 1, 2]), max_outputs=config[2])

        # reshape x to a 4d tensor
        x_image = tf.reshape(x, [-1, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS])

        # convolve x_image with the weight tensor, add the bias, apply the ReLU function, and finally max pool
        h_conv1 = CONV1_ACTIV_FUNC(conv2d(x_image, W_conv1, CONV1_STRIDE, CONV1_PADDING) + b_conv1)
        h_pool1 = max_pool_2x2(h_conv1, POOL1_FILTER_SIZE, POOL1_STRIDE, POOL1_PADDING)

        # second convolutional layer
        W_conv2 = weight_variable([config[1][0], config[1][1], config[2], config[3]], 'W_conv2')
        b_conv2 = bias_variable([config[3]], 'b_conv2')

        tf.summary.image('W_conv2', tf.transpose(W_conv2[:, :, 0:1, :], [3, 0, 1, 2]), max_outputs=config[3])

        # convolve the result of h_pool1 with the weight tensor, add the bias, apply the ReLU function, and finally max pool
        h_conv2 = CONV2_ACTIV_FUNC(conv2d(h_pool1, W_conv2, CONV2_STRIDE, CONV2_PADDING) + b_conv2)
        h_pool2 = max_pool_2x2(h_conv2, POOL2_FILTER_SIZE, POOL2_STRIDE, POOL2_PADDING)

        # densely connected layer
        p2s = h_pool2.get_shape().as_list()
        W_fc1 = weight_variable([p2s[1]*p2s[2]*config[3], FC1_NUM_NEURONS], 'W_fc1')
        b_fc1 = bias_variable([FC1_NUM_NEURONS], 'b_fc1')

        h_pool2_flat = tf.reshape(h_pool2, [-1, p2s[1]*p2s[2]*config[3]])
        h_fc1 = FC1_ACTIV_FUNC(tf.matmul(h_pool2_flat, W_fc1) + b_fc1)

        # dropout
        h_fc1_drop = tf.nn.dropout(h_fc1, keep_prob)

        # readout layer
        W_fc2 = weight_variable([FC1_NUM_NEURONS, NUM_CLASSES], 'W_fc2')
        b_fc2 = bias_variable([NUM_CLASSES], 'b_fc2')

        y_conv = tf.matmul(h_fc1_drop, W_fc2) + b_fc2

        # setup for training
        cross_entropy = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y_conv))
        train_step = tf.train.AdamOptimizer(learning_rate=LEARNING_RATE).minimize(cross_entropy)
        correct_prediction = tf.equal(tf.argmax(y_conv,1), tf.argmax(y_,1))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

        # setup to save accuracy and loss to logs
        tf.summary.scalar("accuracy", accuracy)
        tf.summary.scalar("cross_entropy", cross_entropy)
        merged = tf.summary.merge_all()
        train_writer = tf.summary.FileWriter(log_dir + 'train/', sess.graph)
        validation_writer = tf.summary.FileWriter(log_dir + 'validation', sess.graph)

        saver = tf.train.Saver()

        sess.run(tf.global_variables_initializer())

        step_list = []
        loss_list = []
        val_acc_list = []
        k = 0
        for i in range(NUM_ITERS):
            j = 0
            while (j + BATCH_SIZE <= train_data.shape[0]):
                batch = [train_data[j:j+BATCH_SIZE], train_labels[j:j+BATCH_SIZE]]
                summary, _ = sess.run([merged, train_step], feed_dict={x: batch[0], y_: batch[1], keep_prob: config[4]})
                train_writer.add_summary(summary, k)
                j += BATCH_SIZE
                k += 1

            if i % 10 == 0:
                summary, loss, acc = sess.run([merged, cross_entropy, accuracy], feed_dict={x: validation_data, y_: validation_labels, keep_prob: 1.0})
                validation_writer.add_summary(summary, k)
                print("Step %d, validation accuracy %g"%(i, acc))
                step_list.append(i)
                loss_list.append(loss)
                val_acc_list.append(acc)
                save_path = saver.save(sess, model_dir + model_name + ".ckpt")
                print("Saved model %s at Step %d"%(model_name, i))

        acc, y_c = sess.run([accuracy, y_conv], feed_dict={x: test_data, y_: test_labels, keep_prob: 1.0})

        # print("Final predictions",y_c)
        print("Final test accuracy for %s is %g"%(model_name, acc))

        save_path = saver.save(sess, model_dir + model_name + ".ckpt")
        print("Saved final %s to path %s: "%(model_name, save_path))

        # print current lists of experiment values
        print "step_list:", step_list
        print "loss_list:", loss_list
        print "val_acc_list:", val_acc_list

        print "\n"

        # write experiment output to file -- flag 'a' for append
        config_dict = OrderedDict(zip(config_names, config))
        with open("experiment_output.txt", 'a') as f:
            f.write(model_name + '\n\n')
            f.write("experiment end time: " + str(datetime.now()) + '\n\n')
            f.write("configuration:\n")
            for c in config_dict:
                f.write(c + ' = ' + str(config_dict[c]) + '\n')
            f.write("\nstep:\n")
            f.write(','.join([str(s) for s in step_list]))
            f.write("\nloss:\n")
            f.write(','.join([str(l) for l in loss_list]))
            f.write("\nvalidation accuracy:\n")
            f.write(','.join([str(a) for a in val_acc_list]))
            f.write("\ntest accuracy:\n")
            f.write(str(acc))
            f.write("\n\n")
            f.write("--------------------")
            f.write("\n\n")

        train_writer.close()
        validation_writer.close()
