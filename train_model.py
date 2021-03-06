import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pickle
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import cross_val_score, StratifiedShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler

df = pd.read_csv('data/on_screen_look_data.csv')
df.drop_duplicates(keep='first', inplace=True)
df.reset_index(drop=True, inplace=True)
#print(df)

min_max = MinMaxScaler()
df[['x1', 'x2', 'x3']] = min_max.fit_transform(df[['x1', 'x2', 'x3']])
#print(df)
pickle.dump(min_max, open('models/looking-at-screen-detector/normalizer.blob', 'wb'))

#print(df.describe())
#df.hist()
#plt.show()
#train_set, test_set = train_test_split(df, test_size = 0.2, random_state=42)
#print(train_set)
#print(test_set)
split = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
for train_indices, test_indices in split.split(df, df["y"]):
    train_set = df.loc[train_indices]
    test_set = df.loc[test_indices]
#print(train_set)
#print(test_set)
train_x = train_set.drop("y", axis=1)
train_y = train_set["y"].copy()

test_x = test_set.drop("y", axis=1)
test_y = test_set["y"].copy()
#train_x[['x1', 'x2', 'x3']] = min_max.fit_transform(train_x[['x1', 'x2', 'x3']])

print(train_x)
print(train_y)

sgd_clf = SGDClassifier(random_state=42)
sgd_clf.fit(train_x, train_y)

print(test_x)
print(test_x.loc[[0]])
print(test_y.loc[0])
print(sgd_clf.predict(test_x.loc[[0]]))

print(cross_val_score(sgd_clf, train_x, train_y, cv=3, scoring='accuracy'))

print(train_set.describe())

print(len(train_set[(train_set['y'] == 1)]))
print(len(train_set[(train_set['y'] == 0)]))

print(cross_val_score(sgd_clf, test_x, test_y, cv=3, scoring='accuracy'))

pickle.dump(sgd_clf, open('models/looking-at-screen-detector/looking-at-screen-detector.blob', 'wb'))

