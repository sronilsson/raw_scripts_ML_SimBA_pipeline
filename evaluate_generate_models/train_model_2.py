from configparser import ConfigParser
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from yellowbrick.classifier import ClassificationReport
from xgboost.sklearn import XGBClassifier
from imblearn.combine import SMOTEENN
from imblearn.over_sampling import SMOTE
from sklearn import metrics
from sklearn.tree import export_graphviz
from subprocess import call
import pickle
import csv
import numpy as np
import eli5
from eli5.sklearn import PermutationImportance
import matplotlib.pyplot as plt
from sklearn.model_selection import learning_curve
from sklearn.model_selection import ShuffleSplit
from sklearn.metrics import precision_recall_curve, average_precision_score
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None

configFile = r"Z:\DeepLabCut\DLC_extract\New_102519\project_folder\project_config.ini"
config = ConfigParser()
config.read(configFile)
modelDir = config.get('SML settings', 'model_dir')
modelDir_out = os.path.join(modelDir, 'generated_models')
if not os.path.exists(modelDir_out):
    os.makedirs(modelDir_out)
tree_evaluations_out = os.path.join(modelDir_out, 'model_evaluations')
if not os.path.exists(tree_evaluations_out):
    os.makedirs(tree_evaluations_out)
model_nos = config.getint('SML settings', 'No_targets')
data_folder = config.get('create ensemble settings', 'data_folder')
model_to_run = config.get('create ensemble settings', 'model_to_run')
classifierName = config.get('create ensemble settings', 'classifier')
under_sample_setting = config.get('create ensemble settings', 'under_sample_setting')
under_sample_ratio = config.getfloat('create ensemble settings', 'under_sample_ratio')
over_sample_setting = config.get('create ensemble settings', 'over_sample_setting')
over_sample_ratio = config.getfloat('create ensemble settings', 'over_sample_ratio')
train_test_size = config.getfloat('create ensemble settings', 'train_test_size')
log_path = config.get('General settings', 'project_path')
log_path = os.path.join(log_path, 'project_folder', 'logs')
targetFrame = pd.DataFrame()
features = pd.DataFrame()

def generateClassificationReport(clf, class_names):
    try:
        visualizer = ClassificationReport(clf, classes=class_names, support=True)
        visualizer.score(data_test, target_test)
        visualizerPath = os.path.join(tree_evaluations_out, str(classifierName) + '_classificationReport.png')
        g = visualizer.poof(outpath=visualizerPath)
    except KeyError:
        print(('Warning, not enough data for classification report: ') + str(classifierName))

def generateFeatureImportanceLog(importances):
    feature_importances = [(feature, round(importance, 2)) for feature, importance in zip(feature_list, importances)]
    feature_importances = sorted(feature_importances, key=lambda x: x[1], reverse=True)
    feature_importance_list = [('Variable: {:20} Importance: {}'.format(*pair)) for pair in feature_importances]
    feature_importance_list_varNm = [i.split(':' " ", 3)[1] for i in feature_importance_list]
    feature_importance_list_importance = [i.split(':' " ", 3)[2] for i in feature_importance_list]
    log_df = pd.DataFrame()
    log_df['Feature_name'] = feature_importance_list_varNm
    log_df['Feature_importance'] = feature_importance_list_importance
    logPath = os.path.join(log_path, str(classifierName) + '_feature_importance_log.csv')
    log_df.to_csv(logPath)
    return log_df

def generateFeatureImportanceBarGraph(log_df, N_feature_importance_bars):
    log_df['Feature_importance'] = log_df['Feature_importance'].apply(pd.to_numeric)
    log_df['Feature_name'] = log_df['Feature_name'].map(lambda x: x.lstrip('+-').rstrip('Importance'))
    log_df = log_df.head(N_feature_importance_bars)
    ax = log_df.plot.bar(x='Feature_name', y='Feature_importance', legend=False, rot=90, fontsize=6)
    figName = str(classifierName) + '_feature_bars.png'
    figSavePath = os.path.join(tree_evaluations_out, figName)
    plt.tight_layout()
    plt.savefig(figSavePath, dpi=600)
    plt.close('all')

def generateExampleDecisionTree(estimator):
    dot_name = os.path.join(tree_evaluations_out, str(classifierName) + '_tree.dot')
    file_name = os.path.join(tree_evaluations_out, str(classifierName) + '_tree.pdf')
    export_graphviz(estimator, out_file=dot_name, filled=True, rounded=True, special_characters=False, impurity=False,
                    class_names=class_names, feature_names=data_train.columns)
    commandStr = ('dot ' + str(dot_name) + ' -T pdf -o ' + str(file_name) + ' -Gdpi=600')
    call(commandStr, shell=True)

def generateMetaData(metaDataList):
    metaDataFn = str(classifierName) + '_meta.csv'
    metaDataPath = os.path.join(modelDir_out, metaDataFn)
    print(metaDataPath)
    metaDataHeaders = ["Classifier_name", "Ensamble_method", "Under_sampling_setting", "Under_sampling_ratio", "Over_sampling_method", "Over_sampling_ratio", "Estimators", "Max_features", "RF_criterion", "RF_min_sample_leaf",  "train_test_ratio", "Feature_list"]
    with open(metaDataPath, 'w', newline='') as f:
        out_writer = csv.writer(f)
        out_writer.writerow(metaDataHeaders)
        out_writer.writerow(metaDataList)

def computePermutationImportance(data_test, target_test, clf):
    perm = PermutationImportance(clf, random_state=1).fit(data_test, target_test)
    permString = (eli5.format_as_text(eli5.explain_weights(perm, feature_names=data_test.columns.tolist())))
    permString = permString.split('\n',9)[-1]
    all_rows = permString.split("\n")
    all_cols = [row.split(' ') for row in all_rows]
    all_cols.pop(0)
    fimp = [row[0] for row in all_cols]
    errot = [row[2] for row in all_cols]
    name = [row[4] for row in all_cols]
    dfvals = pd.DataFrame(list(zip(fimp, errot, name)), columns=['A', 'B', 'C'])
    fname = os.path.join(tree_evaluations_out, str(classifierName) + '_permutations_importances.csv')
    dfvals.to_csv(fname, index=False)

def LearningCurve(features, targetFrame, shuffle_splits, dataset_splits):
    cv = ShuffleSplit(n_splits=shuffle_splits, test_size=0.2, random_state=0)
    model = RandomForestClassifier(n_estimators=2000, max_features=RF_max_features, n_jobs=-1, criterion=RF_criterion, min_samples_leaf=RF_min_sample_leaf, bootstrap=True, verbose=0)
    train_sizes, train_scores, test_scores = learning_curve(model, features, targetFrame, cv=cv, scoring='f1', shuffle=True, n_jobs=-1, train_sizes=np.linspace(0.01, 1.0, dataset_splits))
    train_sizes = np.linspace(0.01, 1.0, dataset_splits)
    train_mean = np.mean(train_scores, axis=1)
    test_mean = np.mean(test_scores, axis=1)
    train_std = np.std(train_scores, axis=1)
    test_std = np.std(test_scores, axis=1)
    learningCurve_df = pd.DataFrame()
    learningCurve_df['Fraction Train Size'] = train_sizes
    learningCurve_df['Train_mean_f1'] = train_mean
    learningCurve_df['Test_mean_f1'] = test_mean
    learningCurve_df['Train_std_f1'] = train_std
    learningCurve_df['Test_std_f1'] = test_std
    fname = os.path.join(tree_evaluations_out, str(classifierName) + '_learning_curve.csv')
    learningCurve_df.to_csv(fname, index=False)

#READ IN DATA FOLDER AND REMOVE ALL NON-FEATURE VARIABLES (POP DLC COORDINATE DATA AND TARGET DATA)
for i in os.listdir(data_folder):
    if i.__contains__(".csv"):
        currentFn = os.path.join(data_folder, i)
        df = pd.read_csv(currentFn, index_col=False)
        features = features.append(df, ignore_index=True)
        print(str(i) + ' appended to model dataframe...')
features = features.loc[:, ~features.columns.str.contains('^Unnamed')]
frame_number = features.pop('frames').values
video_number = features.pop('video_no').values
targetFrame = features.pop(classifierName).values
features = features.fillna(0)
features = features.drop(["scorer", "Ear_left_1_x", "Ear_left_1_y", "Ear_left_1_p", "Ear_right_1_x", "Ear_right_1_y", "Ear_right_1_p", "Nose_1_x", "Nose_1_y", "Nose_1_p", "Center_1_x", "Center_1_y", "Center_1_p", "Lat_left_1_x", "Lat_left_1_y",
            "Lat_left_1_p", "Lat_right_1_x", "Lat_right_1_y", "Lat_right_1_p", "Tail_base_1_x", "Tail_base_1_y", "Tail_base_1_p", "Tail_end_1_x", "Tail_end_1_y", "Tail_end_1_p", "Ear_left_2_x",
            "Ear_left_2_y", "Ear_left_2_p", "Ear_right_2_x", "Ear_right_2_y", "Ear_right_2_p", "Nose_2_x", "Nose_2_y", "Nose_2_p", "Center_2_x", "Center_2_y", "Center_2_p", "Lat_left_2_x", "Lat_left_2_y",
            "Lat_left_2_p", "Lat_right_2_x", "Lat_right_2_y", "Lat_right_2_p", "Tail_base_2_x", "Tail_base_2_y", "Tail_base_2_p", "Tail_end_2_x", "Tail_end_2_y", "Tail_end_2_p"], axis=1)
target_names = []
loop=1
for i in range(model_nos):
    currentModelNames = 'target_name_' + str(loop)
    currentModelNames = config.get('SML settings', currentModelNames)
    if currentModelNames != classifierName:
        target_names.append(currentModelNames)
    loop+=1
loop = 0
for i in range(len(target_names)):
    currentModelName = target_names[i]
    features.pop(currentModelName).values
class_names = class_names = ['Not_' + classifierName, classifierName]
feature_list = list(features.columns)

#IF SET BY USER - PERFORM UNDERSAMPLING AND OVERSAMPLING IF SET BY USER
data_train, data_test, target_train, target_test = train_test_split(features, targetFrame, test_size=train_test_size)
if under_sample_setting == 'Random undersample':
    print('Performing undersampling..')
    trainDf = data_train
    trainDf[classifierName] = target_train
    targetFrameRows = trainDf.loc[trainDf[classifierName] == 1]
    nonTargetFrameRows = trainDf.loc[trainDf[classifierName] == 0]
    nontargetFrameRowsSize = int(len(targetFrameRows) * under_sample_ratio)
    nonTargetFrameRows = nonTargetFrameRows.sample(nontargetFrameRowsSize, replace=False)
    trainDf = pd.concat([targetFrameRows, nonTargetFrameRows])
    target_train = trainDf.pop(classifierName).values
    data_train = trainDf
if over_sample_setting == 'SMOTEENN':
    print('Performing SMOTEEN oversampling..')
    smt = SMOTEENN(sampling_strategy=over_sample_ratio)
    data_train, target_train = smt.fit_sample(data_train, target_train)
if over_sample_setting == 'SMOTE':
    print('Performing SMOTE oversampling..')
    smt = SMOTE(sampling_strategy=over_sample_ratio)
    data_train, target_train = smt.fit_sample(data_train, target_train)

# RUN THE DECISION ENSEMBLE SET BY THE USER
#run random forest
if model_to_run == 'RF':
    RF_n_estimators = config.getint('create ensemble settings', 'RF_n_estimators')
    RF_max_features = config.get('create ensemble settings', 'RF_max_features')
    RF_criterion = config.get('create ensemble settings', 'RF_criterion')
    RF_min_sample_leaf = config.getint('create ensemble settings', 'RF_min_sample_leaf')
    RF_n_jobs = config.getint('create ensemble settings', 'RF_n_jobs')
    clf = RandomForestClassifier(n_estimators=RF_n_estimators, max_features=RF_max_features, n_jobs=-1, criterion=RF_criterion, min_samples_leaf=RF_min_sample_leaf, bootstrap=True, verbose=1)
    clf.fit(data_train, target_train)
    clf_pred = clf.predict(data_test)
    print("Accuracy " + str(classifierName) + ' model:', metrics.accuracy_score(target_test, clf_pred))

    # #RUN RANDOM FOREST EVALUATIONS
    compute_permutation_importance = config.get('create ensemble settings', 'compute_permutation_importance')
    if compute_permutation_importance == 'yes':
        computePermutationImportance(data_test, target_test, clf)
    generate_learning_curve = config.get('create ensemble settings', 'generate_learning_curve')
    if generate_learning_curve == 'yes':
        shuffle_splits = config.getint('create ensemble settings', 'LearningCurve_shuffle_k_splits')
        dataset_splits = config.getint('create ensemble settings', 'LearningCurve_shuffle_data_splits')
        LearningCurve(features, targetFrame, shuffle_splits, dataset_splits)

    generate_precision_recall_curve = config.get('create ensemble settings', 'generate_precision_recall_curve')
    if generate_precision_recall_curve == 'yes':
        precisionRecallDf = pd.DataFrame()
        probabilities = clf.predict_proba(data_test)[:,1]
        precision, recall, _ = precision_recall_curve(target_test, probabilities, pos_label=1)
        average_precision = average_precision_score(target_test, probabilities)
        precisionRecallDf['precision'] = precision
        precisionRecallDf['recall'] = recall
        # precisionRecallDf = precisionRecallDf.round(5)
        # precisionRecallDf = precisionRecallDf.drop_duplicates('precision')
        PRCpath = os.path.join(tree_evaluations_out, str(classifierName) + '_precision_recall.csv')
        precisionRecallDf.to_csv(PRCpath)

    generate_example_decision_tree = config.get('create ensemble settings', 'generate_example_decision_tree')
    if generate_example_decision_tree == 'yes':
        estimator = clf.estimators_[3]
        generateExampleDecisionTree(estimator)

    generate_classification_report = config.get('create ensemble settings', 'generate_classification_report')
    if generate_classification_report == 'yes':
        generateClassificationReport(clf, class_names)

    generate_features_importance_log = config.get('create ensemble settings', 'generate_features_importance_log')
    if generate_features_importance_log == 'yes':
        importances = list(clf.feature_importances_)
        log_df = generateFeatureImportanceLog(importances)

    generate_features_importance_bar_graph = config.get('create ensemble settings', 'generate_features_importance_bar_graph')
    N_feature_importance_bars = config.getint('create ensemble settings', 'N_feature_importance_bars')
    if generate_features_importance_bar_graph == 'yes':
        generateFeatureImportanceBarGraph(log_df, N_feature_importance_bars)

    # SAVE MODEL META DATA
    RF_meta_data = config.get('create ensemble settings', 'RF_meta_data')
    if RF_meta_data == 'yes':
        metaDataList = [classifierName, model_to_run, under_sample_setting, under_sample_ratio, over_sample_setting, over_sample_ratio, RF_n_estimators, RF_max_features, RF_criterion, RF_min_sample_leaf, class_names, train_test_size, feature_list]
        generateMetaData(metaDataList)

#run gradient boost model
if model_to_run == 'GBC':
    GBC_n_estimators = config.getint('create ensemble settings', 'GBC_n_estimators')
    GBC_max_features = config.get('create ensemble settings', 'GBC_max_features')
    GBC_max_depth = config.getint('create ensemble settings', 'GBC_max_depth')
    GBC_learning_rate = config.getfloat('create ensemble settings', 'GBC_learning_rate')
    GBC_min_sample_split = config.getint('create ensemble settings', 'GBC_min_sample_split')
    clf = GradientBoostingClassifier(max_depth=GBC_max_depth, n_estimators=GBC_n_estimators, learning_rate=GBC_learning_rate, max_features=GBC_max_features, min_samples_split=GBC_min_sample_split, verbose=1)
    clf.fit(data_train, target_train)
    clf_pred = clf.predict(data_test)
    print(str(classifierName) + str(" Accuracy train: ") + str(clf.score(data_train, target_train)))

    generate_example_decision_tree = config.get('create ensemble settings', 'generate_example_decision_tree')
    if generate_example_decision_tree == 'yes':
        estimator = clf.estimators_[3,0]
        generateExampleDecisionTree(estimator)

    generate_classification_report = config.get('create ensemble settings', 'generate_classification_report')
    if generate_classification_report == 'yes':
        generateClassificationReport(clf, class_names)

    generate_features_importance_log = config.get('create ensemble settings', 'generate_features_importance_log')
    if generate_features_importance_log == 'yes':
        importances = list(clf.feature_importances_)
        log_df = generateFeatureImportanceLog(importances)

    generate_features_importance_bar_graph = config.get('create ensemble settings', 'generate_features_importance_bar_graph')
    N_feature_importance_bars = config.getint('create ensemble settings', 'N_feature_importance_bars')
    if generate_features_importance_bar_graph == 'yes':
        generateFeatureImportanceBarGraph(log_df, N_feature_importance_bars)

#run XGboost
if model_to_run == 'XGB':
    XGB_n_estimators = config.getint('create ensemble settings', 'XGB_n_estimators')
    XGB_max_depth = config.getint('create ensemble settings', 'GBC_max_depth')
    XGB_learning_rate = config.getfloat('create ensemble settings', 'XGB_learning_rate')
    clf = XGBClassifier(max_depth=XGB_max_depth, min_child_weight=1, learning_rate=XGB_learning_rate, n_estimators=XGB_n_estimators,
                            silent=0, objective='binary:logistic', max_delta_step=0, subsample=1, colsample_bytree=1,
                            colsample_bylevel=1, reg_alpha=0, reg_lambda=0, scale_pos_weight=1, seed=1, missing=None,
                            verbosity=3)
    clf.fit(data_train, target_train, verbose=True)
    clf_pred = clf.predict(data_test)
    print(str(classifierName) + str(" Accuracy train: ") + str(clf.score(data_train, target_train)))
    print(str(classifierName) + str(" Accuracy test: ") + str(clf.score(data_test, target_test)))


#SAVE MODEL
modelfn = str(classifierName) + '.sav'
modelPath = os.path.join(modelDir_out, modelfn)
pickle.dump(clf, open(modelPath, 'wb'))
print('Classifier ' + str(classifierName) + ' saved @' + str(modelPath))


