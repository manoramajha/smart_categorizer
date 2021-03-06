import numpy as np
from keras.applications.resnet50 import ResNet50
from keras.applications.resnet50 import preprocess_input
from keras.preprocessing import image
import tqdm
import glob
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score
import os
import shutil
import argparse
import sys

parser = argparse.ArgumentParser(description='Trainable categorization tool')
parser.add_argument(
        '--positives',
        type=str,
        help='Directory containing positive images to train on',
        required=True
)
parser.add_argument(
        '--negatives',
        type=str,
        help='(Optional) Directory containing negative images to train on',
        required=False
)
parser.add_argument(
        '--target_data',
        type=str,
        help='Path to dir containing uncategorized data',
        required=True
)
parser.add_argument(
        '--save_to',
        type=str,
        help='Path to save categorized data',
        required=True
)

args = parser.parse_args()


def chunks(l, n):
    return [l[i:i + n] for i in xrange(0, len(l), n)]


def list_images(dst_dir, exts='jpg,JPEG,gif,png'):
    paths = []
    for ext in exts.split(','):
        paths.extend(glob.glob(dst_dir.rstrip('/') + '/*.%s' % ext))
    return paths


def get_rand_subset(data, n):
    ids = range(len(data))
    subset = np.random.choice(ids, size=n, replace=False)
    return data[subset]


def get_dataset(pos, all_neg, hard_negative=None):
    pos_y = np.array([1] * len(pos))
    neg = []
    if hard_negative is not None:
        neg.extend(hard_negative)

    if len(neg) < 2 * len(pos):
        nums_of_neg = min(2 * len(pos) - len(neg), len(all_neg))
        neg.extend(get_rand_subset(all_neg, nums_of_neg))

    neg = np.array(neg)
    neg_y = np.array([0] * len(neg))

    print "Number of positive examples: " + str(pos.shape[0])
    print "Number of negative examples: " + str(neg.shape[0])

    X = np.vstack([pos, neg])
    y = np.hstack([pos_y, neg_y])
    return train_test_split(X, y, test_size=0.1)


def classify(paths, pos_dir):
    features = get_features(paths)
    probs = clf.predict(features)
    ids = np.where(probs)[0]
    pos_paths = [paths[idx] for idx in ids]
    if not os.path.exists(pos_dir):
        os.makedirs(pos_dir)
    print 'Saving result...'
    for p in pos_paths:
        shutil.copy(p, pos_dir)


def get_features(paths):
    features = []
    for batch in tqdm.tqdm(chunks(paths, 16)):
        imgs = [image.img_to_array(image.load_img(f, target_size=(224, 224))) for f in batch]
        imgs = np.array(imgs)
        x = preprocess_input(imgs)
        preds = model.predict(x)
        features.extend(preds[:,0,0,:])
    return np.array(features)

if __name__ == '__main__':
    model = ResNet50(weights='imagenet', include_top=False)
    negative_features = np.load('data/neg_f_1000.npy')
    raw_data_paths = list_images(args.target_data)
    if len(raw_data_paths) == 0:
        print 'No data found to categorize in path: %s' % args.target_data
        sys.exit(1)

    pos_paths = list_images(args.positives)
    print 'Processing positives images...'
    pos_features = get_features(pos_paths)

    hard_neg_features = None
    if args.negatives and os.path.exists(args.negatives):
        print 'Processing negative images...'
        hard_neg_paths = list_images(args.negatives)
        hard_neg_features = get_features(hard_neg_paths)

    clf = LinearSVC()
    X_train, X_test, y_train, y_test = get_dataset(pos_features, negative_features, hard_neg_features)
    print 'Training'
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    print 'Training finished. Accuracy score: %f' % accuracy_score(y_test, y_pred)
    print 'Categorizing target images'
    classify(raw_data_paths, args.save_to)
    print 'Done!'


