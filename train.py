#!/usr/bin/env python

import os, glob, sys, csv, math, random, datetime, pickle
import numpy as np
import tensorflow as tf
from sklearn.cluster import KMeans

from data              import Data
from baseline          import Baseline,         BaselineCosine
from negative_hyponym  import NegativeHyponym,  NegativeHyponymCosine
from negative_hypernym import NegativeHypernym, NegativeHypernymCosine
from negative_synonym  import NegativeSynonym,  NegativeSynonymCosine

flags = tf.app.flags
FLAGS = flags.FLAGS

flags.DEFINE_string( 'model', 'baseline', 'Model name.')
flags.DEFINE_integer('seed',         228, 'Random seed.')
flags.DEFINE_integer('num_epochs',  8000, 'Number of training epochs.')
flags.DEFINE_integer('batch_size',   512, 'Batch size.')
flags.DEFINE_boolean('gpu',         True, 'Try using GPU.')

def model_class(name):
    name = name.lower()
    if name.lower() == 'baseline':
        return Baseline
    elif name.lower() == 'baseline_cosine':
        return BaselineCosine
    elif name.lower() == 'negative_hyponym':
        return NegativeHyponym
    elif name.lower() == 'negative_hyponym_cosine':
        return NegativeHyponymCosine
    elif name.lower() == 'negative_hypernym':
        return NegativeHypernym
    elif name.lower() == 'negative_hypernym_cosine':
        return NegativeHypernymCosine
    elif name.lower() == 'negative_synonym':
        return NegativeSynonym
    elif name.lower() == 'negative_synonym_cosine':
        return NegativeSynonymCosine
    else:
        raise LookupError(name)

def train(config, model, data):
    train_op = tf.train.AdamOptimizer(epsilon=1.).minimize(model.loss)

    train_losses, test_losses = [], []
    train_times = []

    with tf.Session(config=config) as sess:
        init_op = tf.initialize_all_variables()
        sess.run(init_op)

        feed_dict_train, feed_dict_test = {
            model.X: data.X_train,
            model.Y: data.Y_train,
            model.Z: data.Z_train()
        }, {
            model.X: data.X_test,
            model.Y: data.Y_test,
            model.Z: data.Z_test()
        }

        print('Cluster %d: %d train items and %d test items available.' % (
            data.cluster + 1, data.X_train.shape[0], data.X_test.shape[0]))

        for step in range(0, FLAGS.num_epochs):
            batch = np.random.randint(0, data.X_train.shape[0], FLAGS.batch_size)

            feed_dict = {
                model.X: data.X_train[batch, :],
                model.Y: data.Y_train[batch, :],
                model.Z: data.Z_train(batch)
            }

            t_this = datetime.datetime.now()
            sess.run(train_op, feed_dict=feed_dict)
            t_last = datetime.datetime.now()
            train_times.append(t_last - t_this)

            if (step + 1) % 500 == 0:
                train_losses.append(sess.run(model.loss, feed_dict=feed_dict_train))
                test_losses.append(sess.run(model.loss, feed_dict=feed_dict_test))
                print('Cluster %d: step = %05d, train loss = %f, test loss = %f.' % (
                    data.cluster + 1, step + 1, train_losses[-1], test_losses[-1]))

        print('Cluster %d done in %s.' % (data.cluster + 1, str(sum(train_times, datetime.timedelta()))))
        return sess.run(model.W)

def main(_):
    random.seed(FLAGS.seed)
    tf.set_random_seed(FLAGS.seed)

    config = tf.ConfigProto() if FLAGS.gpu else tf.ConfigProto(device_count={'GPU': 0})

    with np.load('train-vectors.npz') as npz:
        X_all_train,   Y_all_train = npz['X_all_train'],   npz['Y_all_train']
        Z_index_train, Z_all_train = npz['Z_index_train'], npz['Z_all_train']

    with np.load('test-vectors.npz') as npz:
        X_all_test,   Y_all_test = npz['X_all_test'],   npz['Y_all_test']
        Z_index_test, Z_all_test = npz['Z_index_test'], npz['Z_all_test']

    kmeans = pickle.load(open('kmeans.pickle', 'rb'))

    clusters_train = kmeans.predict(Y_all_train - X_all_train)
    clusters_test  = kmeans.predict(Y_all_test  - X_all_test)

    model = model_class(FLAGS.model)(x_size=X_all_train.shape[1], y_size=Y_all_train.shape[1])
    print('The model class is %s.' % (type(model).__name__))

    for path in glob.glob('%s.W-*.txt' % (FLAGS.model)):
        print('Removing a stale file: "%s".' % path)
        os.remove(path)

    for cluster in range(kmeans.n_clusters):
        data = Data(cluster, clusters_train, clusters_test,
                    X_all_train, Y_all_train, Z_index_train, Z_all_train,
                    X_all_test,  Y_all_test,  Z_index_test,  Z_all_test)
        W    = train(config, model, data)
        np.savetxt('%s.W-%d.txt' % (FLAGS.model, cluster + 1), W)

if __name__ == '__main__':
    tf.app.run()