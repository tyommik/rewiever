#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import distutils.spawn
import os.path
import platform
import re
import sys
import subprocess
# import cv2
from functools import partial
from collections import defaultdict
import pathlib

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except ImportError:
    # needed for py3+qt4
    # Ref:
    # http://pyqt.sourceforge.net/Docs/PyQt4/incompatible_apis.html
    # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string
    if sys.version_info.major >= 3:
        import sip
        sip.setapi('QVariant', 2)
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

# import resources
# Add internal libs
from libs.constants import *
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut, generateColorByText
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.toolBar import ToolBar
from libs.timeline import Timeline
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_cache_io import YoloCacheReader, CACHE_EXT
from libs.yolo_io import TXT_EXT
from libs.ustr import ustr
from libs.version import __version__
from libs.hashableQListWidgetItem import HashableQListWidgetItem
import config
from libs.video_processing import VideoCapture


__appname__ = 'labelVid'
POS = 20

# Utility functions and classes.

def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))

def util_qt_strlistclass():
    return QStringList if have_qstring() else list


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(self, defaultFilename=None, defaultPrefdefClassFile=None, defaultSaveDir=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        # Load string bundle for i18n
        self.stringBundle = StringBundle.getBundle()
        getStr = lambda strId: self.stringBundle.getString(strId)

        # Save as Yolo xml
        self.defaultSaveDir = defaultSaveDir
        self.usingPascalVocFormat = False
        self.usingYoloFormat = True

        # For loading all image under a directory
        self.mFrameList = []
        self.mVideoList = []
        self.dirname = None
        self.labelHist = []
        self.lastOpenDir = None

        # Whether we need to save or not.
        self.dirty = False

        # Shapes
        self.shapes = None

        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = self.getAvailableScreencastViewer()
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.loadPredefinedClasses(defaultPrefdefClassFile)

        # Main widgets and related state.
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)

        self.itemsToShapes = {}
        self.shapesToItems = {}
        self.prevLabelText = ''
        self.propagateStartFrame = None
        self.propagateLabelsFlag = False
        self.propagateLabels = []

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        self.useDefaultLabelCheckbox = QCheckBox(getStr('useDefaultLabel'))
        self.useDefaultLabelCheckbox.setChecked(False)
        self.defaultLabelTextLine = QLineEdit()
        useDefaultLabelQHBoxLayout = QHBoxLayout()
        useDefaultLabelQHBoxLayout.addWidget(self.useDefaultLabelCheckbox)
        useDefaultLabelQHBoxLayout.addWidget(self.defaultLabelTextLine)
        useDefaultLabelContainer = QWidget()
        useDefaultLabelContainer.setLayout(useDefaultLabelQHBoxLayout)

        # Create a widget for edit and diffc button
        self.diffcButton = QCheckBox(getStr('useDifficult'))
        self.diffcButton.setChecked(False)
        self.diffcButton.stateChanged.connect(self.btnstate)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to listLayout
        listLayout.addWidget(self.editButton)
        listLayout.addWidget(self.diffcButton)
        listLayout.addWidget(useDefaultLabelContainer)

        # Create and add a widget for showing current label items
        self.labelList = QListWidget()
        labelListContainer = QWidget()
        labelListContainer.setLayout(listLayout)
        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        listLayout.addWidget(self.labelList)

        self.dock = QDockWidget(getStr('boxLabelText'), self)
        self.dock.setObjectName(getStr('labels'))
        self.dock.setWidget(labelListContainer)

        self.frameListWidget = QListWidget()
        self.frameListWidget.itemDoubleClicked.connect(self.frameitemDoubleClicked)
        self.frameListWidget.installEventFilter(self)

        self.fileListWidget = QListWidget()
        self.fileListWidget.setObjectName('Test')
        self.fileListWidget.itemDoubleClicked.connect(self.fileitemDoubleClicked)
        self.fileListWidget.installEventFilter(self)

        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.frameListWidget)
        filelistLayout.addWidget(self.fileListWidget)
        fileListContainer = QWidget()
        fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(getStr('fileList'), self)
        self.filedock.setObjectName(getStr('files'))
        self.filedock.setWidget(fileListContainer)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoomRequest)
        self.canvas.setDrawingShapeToSquare(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.scrollArea = scroll
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        # self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        self.filedock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dockFeatures = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

        # Media
        self.video_cap = None

        # Media control slider
        self.positionSlider = Timeline(Qt.Horizontal, self)
        self.positionSlider.sliderMoved.connect(self.loadFrame)
        self.positionSlider.sliderMoved.connect(self.sliderPositionChanged)

        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        container.setLayout(controlLayout)

        # Timeline
        self.timeline = QDockWidget()
        self.timeline.setWidget(container)
        # self.addDockWidget(Qt.BottomDockWidgetArea, self.timeline)
        self.timeline.setFixedHeight(60)

        self.lbl = QLineEdit(f'00:00:00|{0: >{8}}')
        self.lbl.setReadOnly(True)
        self.lbl.setFixedWidth(70)
        self.lbl.setUpdatesEnabled(True)
        self.lbl.setFixedWidth(150)
        self.lbl.setStyleSheet(self.stylesheet())

        self.elbl = QLineEdit(f'00:00:00|{0: >{8}}')
        self.elbl.setReadOnly(True)
        self.elbl.setFixedWidth(70)
        self.elbl.setUpdatesEnabled(True)
        self.elbl.setFixedWidth(150)
        self.elbl.setStyleSheet(self.stylesheet())


        # Annotation toolbox
        AnnoContainer = QWidget()
        annoToolLayout = QHBoxLayout()
        annoToolLayout.setContentsMargins(0, 0, 0, 0)

        self.annoStartButton = QPushButton()
        self.annoStartButton.setText('Start propagate')
        self.annoStartButton.setStyleSheet("Text-align:center")
        self.annoStartButton.pressed.connect(self.setStartPropagateFrame)

        self.annoEndButton = QPushButton()
        self.annoEndButton.setDisabled(True)
        self.annoEndButton.setText('Stop propagate')
        self.annoEndButton.setStyleSheet("Text-align:center")
        self.annoEndButton.pressed.connect(self.setStopPropagateFrame)

        self.ChangeAllMarksButton = QPushButton()
        self.ChangeAllMarksButton.setDisabled(False)
        self.ChangeAllMarksButton.setText('Все события как это')
        self.ChangeAllMarksButton.setStyleSheet("Text-align:center")
        self.ChangeAllMarksButton.pressed.connect(self.changeObjClass)

        self.shortcut = QShortcut(QKeySequence("Q"), self)
        self.shortcut.activated.connect(self.clearAllMarks)

        self.ClearMarksButton = QPushButton()
        self.ClearMarksButton.setDisabled(False)
        self.ClearMarksButton.setText('Удалить все события')
        self.ClearMarksButton.setStyleSheet("Text-align:center")
        self.ClearMarksButton.pressed.connect(self.clearAllMarks)

        annoToolLayout.addWidget(self.annoStartButton)
        annoToolLayout.addWidget(self.annoEndButton)
        annoToolLayout.addWidget(self.ChangeAllMarksButton)
        annoToolLayout.addWidget(self.ClearMarksButton)
        AnnoContainer.setLayout(annoToolLayout)

        # Сompilation
        controlLayout.addWidget(self.lbl)
        controlLayout.addWidget(self.positionSlider)
        controlLayout.addWidget(self.elbl)

        centralContainer = QWidget()
        centralLayout = QVBoxLayout()
        scroll.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        centralLayout.setContentsMargins(0, 0, 0, 0)

        centralLayout.addWidget(scroll)
        centralLayout.addWidget(AnnoContainer)
        centralLayout.addWidget(self.timeline)
        centralContainer.setLayout(centralLayout)
        self.setCentralWidget(centralContainer)


        # Actions
        action = partial(newAction, self)
        quit = action(getStr('quit'), self.close,
                      'Ctrl+Q', 'quit', getStr('quitApp'))

        # openVideo = action(getStr('openFile'), self.openFile,
        #               'Ctrl+O', 'open', getStr('openFileDetail'))

        openVideo = action(getStr('openDir'), self.openDirVideoDialog,
                         'Ctrl+u', 'open', getStr('openDir'))

        opendir = action(getStr('openDir'), self.openDirDialog,
                         'Ctrl+u', 'open', getStr('openDir'))

        changeSavedir = action(getStr('changeSaveDir'), self.changeSavedirDialog,
                               'Ctrl+r', 'open', getStr('changeSavedAnnotationDir'))

        openAnnotation = action(getStr('openAnnotation'), self.openAnnotationDialog,
                                'Ctrl+Shift+O', 'open', getStr('openAnnotationDetail'))

        openNextImg = action(getStr('nextImg'), self.openNextImg,
                             'd', 'next', getStr('nextImgDetail'))

        openPrevImg = action(getStr('prevImg'), self.openPrevImg,
                             'a', 'prev', getStr('prevImgDetail'))

        verify = action(getStr('verifyImg'), self.verifyImg,
                        'space', 'verify', getStr('verifyImgDetail'))

        save = action(getStr('save'), self.saveFile,
                      'Ctrl+S', 'save', getStr('saveDetail'), enabled=True)

        save_format = action('&PascalVOC', self.change_format,
                      'Ctrl+', 'format_voc', getStr('changeSaveFormat'), enabled=True)

        saveAnno = action(getStr('saveAnno'), self.saveAnnotation,
                        'Ctrl+Shift+S', 'save-anno', getStr('saveAsDetail'), enabled=True)

        saveAnnoAs = action(getStr('saveAnnoAs'), self.saveAnnotationAs,
                        '', 'save-anno-as', getStr('saveAsDetail'), enabled=True)

        close = action(getStr('closeCur'), self.closeFile, 'Ctrl+W', 'close', getStr('closeCurDetail'))

        resetAll = action(getStr('resetAll'), self.resetAll, None, 'resetall', getStr('resetAllDetail'))

        color1 = action(getStr('boxLineColor'), self.chooseColor1,
                        'Ctrl+L', 'color_line', getStr('boxLineColorDetail'))

        createMode = action(getStr('crtBox'), self.setCreateMode,
                            'w', 'new', getStr('crtBoxDetail'), enabled=False)
        editMode = action('&Edit\nRectBox', self.setEditMode,
                          'Ctrl+J', 'edit', u'Move and edit Boxs', enabled=False)

        create = action(getStr('crtBox'), self.createShape,
                        'w', 'new', getStr('crtBoxDetail'), enabled=False)
        delete = action(getStr('delBox'), self.deleteSelectedShape,
                        'Delete', 'delete', getStr('delBoxDetail'), enabled=False)

        copy = action(getStr('copyBox'), self.copySelectedShape,
                      'Ctrl+C', 'copy', getStr('dupBoxDetail'),
                      enabled=False)

        paste = action(getStr('pasteBox'), self.pasteShape,
                      'Ctrl+V', 'paste', getStr('pasteBoxDetail'),
                      enabled=True)

        editor = action(getStr('openInEditor'), self.openInEditor,
                      'Ctrl+G', 'Open In Editor', getStr('openInEditor'),
                      enabled=True)

        advancedMode = action(getStr('advancedMode'), self.toggleAdvancedMode,
                              'Ctrl+Shift+A', 'expert', getStr('advancedModeDetail'),
                              checkable=True)

        hideAll = action('&Hide\nRectBox', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', getStr('hideAllBoxDetail'),
                         enabled=False)
        showAll = action('&Show\nRectBox', partial(self.togglePolygons, True),
                         'Ctrl+Shift+A', 'hide', getStr('showAllBoxDetail'),
                         enabled=False)

        help = action(getStr('tutorial'), self.showTutorialDialog, None, 'help', getStr('tutorialDetail'))
        showInfo = action(getStr('info'), self.showInfoDialog, None, 'help', getStr('info'))

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action(getStr('zoomin'), partial(self.addZoom, 10),
                        'Ctrl++', 'zoom-in', getStr('zoominDetail'), enabled=False)
        zoomOut = action(getStr('zoomout'), partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', getStr('zoomoutDetail'), enabled=False)
        zoomOrg = action(getStr('originalsize'), partial(self.setZoom, 100),
                         'Ctrl+=', 'zoom', getStr('originalsizeDetail'), enabled=False)
        fitWindow = action(getStr('fitWin'), self.setFitWindow,
                           'Ctrl+F', 'fit-window', getStr('fitWinDetail'),
                           checkable=True, enabled=False)
        fitWidth = action(getStr('fitWidth'), self.setFitWidth,
                          'Ctrl+Shift+F', 'fit-width', getStr('fitWidthDetail'),
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut,
                       zoomOrg, fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(getStr('editLabel'), self.editLabel,
                      'Ctrl+E', 'edit', getStr('editLabelDetail'),
                      enabled=False)
        self.editButton.setDefaultAction(edit)

        shapeLineColor = action(getStr('shapeLineColor'), self.chshapeLineColor,
                                icon='color_line', tip=getStr('shapeLineColorDetail'),
                                enabled=False)
        shapeFillColor = action(getStr('shapeFillColor'), self.chshapeFillColor,
                                icon='color', tip=getStr('shapeFillColorDetail'),
                                enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText(getStr('showHide'))
        labels.setShortcut('Ctrl+Shift+L')

        # Lavel list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Draw squares/rectangles
        self.drawSquaresOption = QAction('Draw Squares', self)
        self.drawSquaresOption.setShortcut('Ctrl+Shift+R')
        self.drawSquaresOption.setCheckable(True)
        self.drawSquaresOption.setChecked(settings.get(SETTING_DRAW_SQUARE, False))
        self.drawSquaresOption.triggered.connect(self.toogleDrawSquare)

        # Store actions for further handling.
        self.actions = struct(save=save, save_format=save_format, saveAnno=saveAnno, saveAnnoAs=saveAnnoAs, open=openVideo, close=close, resetAll = resetAll,
                              lineColor=color1, create=create, delete=delete, edit=edit, copy=copy,
                              createMode=createMode, editMode=editMode, advancedMode=advancedMode,
                              shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
                              zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
                              fitWindow=fitWindow, fitWidth=fitWidth,
                              zoomActions=zoomActions,
                              fileMenuActions=(
                                  openVideo, opendir, save, saveAnno, saveAnnoAs, close, resetAll, quit),
                              beginner=(), advanced=(),
                              editMenu=(edit, copy, delete, paste, editor,
                                        None, color1, self.drawSquaresOption),
                              beginnerContext=(create, edit, copy, paste, delete),
                              advancedContext=(createMode, editMode, edit, copy,
                                               delete, shapeLineColor, shapeFillColor),
                              onLoadActive=(
                                  close, create, createMode, editMode),
                              onShapesPresent=(saveAnnoAs, hideAll, showAll))

        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)

        # Auto saving : Enable auto saving if pressing next
        self.autoSaving = QAction(getStr('autoSaveMode'), self)
        self.autoSaving.setCheckable(True)
        self.autoSaving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        # Sync single class mode from PR#106
        self.singleClassMode = QAction(getStr('singleClsMode'), self)
        # self.singleClassMode.setShortcut("Ctrl+Shift+S")
        self.singleClassMode.setCheckable(True)
        self.singleClassMode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.displayLabelOption = QAction(getStr('displayLabel'), self)
        self.displayLabelOption.setShortcut("Ctrl+Shift+P")
        self.displayLabelOption.setCheckable(True)
        self.displayLabelOption.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.displayLabelOption.triggered.connect(self.togglePaintLabelsOption)

        # Add option to jump forward and backward
        self.shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.shortcut.activated.connect(lambda : self.jumpForward(config.NUM_SKIP_FRAMES))
        self.shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        self.shortcut.activated.connect(lambda :self.jumpBackward(config.NUM_SKIP_FRAMES))
        self.shortcut = QShortcut(QKeySequence("Shift+D"), self)
        self.shortcut.activated.connect(lambda : self.jumpForward(5 * config.NUM_SKIP_FRAMES))
        self.shortcut = QShortcut(QKeySequence("Shift+A"), self)
        self.shortcut.activated.connect(lambda :self.jumpBackward(5 * config.NUM_SKIP_FRAMES))
        self.shortcut = QShortcut(QKeySequence("S"), self)
        self.shortcut.activated.connect(self.openNextfile)

        addActions(self.menus.file,
                   (openVideo, openAnnotation, saveAnno, saveAnnoAs, self.menus.recentFiles, save, close, resetAll, quit))
        addActions(self.menus.help, (help, showInfo))
        addActions(self.menus.view, (
            self.autoSaving,
            self.singleClassMode,
            self.displayLabelOption,
            labels, advancedMode, None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            openVideo, verify,  openNextImg, openPrevImg, create, copy, paste, delete, None,
            zoomIn, zoom, zoomOut, fitWindow, fitWidth)

        self.actions.advanced = (
            openVideo, verify, openAnnotation, saveAnno, openNextImg, openPrevImg, save, save_format, None, editor,
            createMode, editMode, None,
            hideAll, showAll)

        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filePath = ustr(defaultFilename)
        self.annoFilePath = None
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.defaultSaveDir is None and saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR))
        Shape.fill_color = self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR))
        self.canvas.setDrawingColor(self.lineColor)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.filePath and os.path.isdir(self.filePath):
            self.queueEvent(partial(self.importDirImages, self.filePath or ""))
        elif self.filePath:
            self.queueEvent(partial(self.loadFile, self.filePath or ""))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # Display cursor coordinates at the right of status bar
        self.labelCoordinates = QLabel('')
        self.statusBar().addPermanentWidget(self.labelCoordinates)

        # Open Dir if deafult file
        if self.filePath and os.path.isdir(self.filePath):
            self.openDirDialog(dirpath=self.filePath)

    def stylesheet(self):
        return """
    QSlider::handle:horizontal 
    {
        background: transparent;
        width: 8px;
    }
    QSlider::groove:horizontal {
        border: 1px solid #444444;
        height: 8px;
             background: qlineargradient(y1: 0, y2: 1,
                                         stop: 0 #2e3436, stop: 1.0 #000000);
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient( y1: 0, y2: 1,
            stop: 0 #729fcf, stop: 1 #2a82da);
        border: 1px solid #777;
        height: 8px;
    }
    QSlider::handle:horizontal:hover {
        background: #2a82da;
        height: 8px;
        width: 8px;
        border: 1px solid #2e3436;
    }
    QSlider::sub-page:horizontal:disabled {
        background: #bbbbbb;
        border-color: #999999;
    }
    QSlider::add-page:horizontal:disabled {
        background: #2a82da;
        border-color: #999999;
    }
    QSlider::handle:horizontal:disabled {
        background: #2a82da;
    }
    QLineEdit
    {
        background: white;
        color: #585858;
        border: 0px solid #076100;
        font-size: 12pt;
        font-weight: bold;
    }
        """

    def openDirVideoDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        self.importDirVideos(targetDirPath)

    def importDirVideos(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.fileListWidget.clear()
        self.mVideoList = self.scanAllVideos(dirpath)
        for imgPath in self.mVideoList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

    def scanAllVideos(self, folderPath):
        extensions = ['.mkv']
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        images.sort(key=lambda x: x.lower())
        return images

    # ---------------------------------------------
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.canvas.setDrawingShapeToSquare(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.setDrawingShapeToSquare(True)

    def eventFilter(self, source, event):
        if (event.type() == QEvent.ContextMenu and source is self.frameListWidget):
            # menu = QMenu()
            # menu.addAction('Make anno using selected')
            # if menu.exec_(event.globalPos()):
            #     item = source.itemAt(event.pos())
            #     self.loadFile(item.text())
            #     copyLabels = self.canvas.shapes.copy()
            #     items = self.frameListWidget.selectedItems()
            #     for item in items:
            #         self.loadFile(item.text())
            #         self.canvas.loadShapes(copyLabels)
            #         self.saveLabels(item.text().rsplit('.', maxsplit=1)[0] + '.txt')
            #         if item != items[-1]:
            #             self.closeFile()
            #     print(item.text())
            return True
        if event.type() == QEvent.KeyPress and \
                event.matches(QKeySequence.InsertParagraphSeparator):
            item = self.frameListWidget.selectedItems()[0]
            self.frameitemDoubleClicked(item)
            self.frameListWidget.setFocus()
        return super().eventFilter(source, event)


    ## Support Functions ##
    def set_format(self, save_format):
        if save_format == FORMAT_PASCALVOC:
            self.actions.save_format.setText(FORMAT_PASCALVOC)
            self.actions.save_format.setIcon(newIcon("format_voc"))
            self.usingPascalVocFormat = True
            self.usingYoloFormat = False
            LabelFile.suffix = XML_EXT

        elif save_format == FORMAT_YOLO:
            self.actions.save_format.setText(FORMAT_YOLO)
            self.actions.save_format.setIcon(newIcon("format_yolo"))
            self.usingPascalVocFormat = False
            self.usingYoloFormat = True
            LabelFile.suffix = TXT_EXT

    def change_format(self):
        if self.usingPascalVocFormat: self.set_format(FORMAT_YOLO)
        elif self.usingYoloFormat: self.set_format(FORMAT_PASCALVOC)

    def noShapes(self):
        return not self.itemsToShapes

    def toggleAdvancedMode(self, value=True):
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        self.editButton.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def setStartPropagateFrame(self):
        if self.video_cap:
            self.propagateLabelsFlag = True
            self.propagateStartFrame = self.video_cap.get_position()
            self.propagateLabels = self.canvas.shapes.copy()
            self.annoStartButton.setText('Started propagate')
            self.annoEndButton.setDisabled(False)
            # self.setDirty()

    def setStopPropagateFrame(self):
        # FIXME сохранять лейблы для текущего кадра?
        if self.propagateLabelsFlag:
            position = self.video_cap.get_position()
            if position > self.propagateStartFrame:
                for frame in range(self.propagateStartFrame + 1, position + 2):
                    self.shapes[frame] = [self.format_shape(shape) for shape in self.propagateLabels]
            # Cleaning
            self.propagateLabelsFlag = False
            self.propagateStartFrame = None
            self.propagateLabels = []
            self.annoStartButton.setText('Start propagate')
            self.annoEndButton.setDisabled(True)
            # self.setClean()

    def clearAllMarks(self):
        self.shapes = YoloCacheReader(classListPath=config.PREDEF_YOLO_CLASSES)
        self.loadFile(self.filePath)

    def changeObjClass(self):
        shapes = self.shapes.getShapes()
        position = self.video_cap.get_position()
        self.saveFile()
        propagate_shapes = self.canvas.shapes.copy()
        for frame in shapes:
            self.shapes[frame] = [self.format_shape(shape) for shape in propagate_shapes]
        self.saveLabels()


    def populateModeActions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.create,) if self.beginner()\
            else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.create.setEnabled(True)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.labelList.clear()
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()
        self.labelCoordinates.clear()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filePath):
        if filePath in self.recentFiles:
            self.recentFiles.remove(filePath)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filePath)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    def getAvailableScreencastViewer(self):
        osName = platform.system()

        if osName == 'Windows':
            return ['C:\\Program Files\\Internet Explorer\\iexplore.exe']
        elif osName == 'Linux':
            return ['xdg-open']
        elif osName == 'Darwin':
            return ['open', '-a', 'Safari']

    ## Callbacks ##
    def showTutorialDialog(self):
        subprocess.Popen(self.screencastViewer + [self.screencast])

    def showInfoDialog(self):
        msg = u'Name:{0} \nApp Version:{1} \n{2} '.format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, u'Information', msg)

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.create.setEnabled(False)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print('Cancel creation.')
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.create.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)
        self.labelSelectionChanged()

    def updateFileMenu(self):
        currFilePath = self.filePath

        def exists(filename):
            if filename is not None:
                return os.path.exists(filename)
        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f !=
                 currFilePath and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self):
        if not self.canvas.editing():
            return
        item = self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            item.setBackground(generateColorByText(text))
            self.setDirty()

    # Tzutalin 20160906 : Add file list and dock to move faster
    def frameitemDoubleClicked(self, item=None):
        currIndex = int(item.text())
        if currIndex < len(self.mFrameList):
            if currIndex in self.mFrameList:
                self.loadFrame(currIndex - 1)

    def openNextfile(self, item=None):
        currIndex = self.mVideoList.index(self.filePath)
        self.annoFilePath = ""
        fileWidgetItem = self.fileListWidget.item(currIndex)
        if currIndex + 1 < len(self.mVideoList):
            filename = self.mVideoList[currIndex + 1]
            if filename:
                self.fileListWidget.scrollToItem(self.fileListWidget.item(currIndex + 1),
                                                  hint=QAbstractItemView.EnsureVisible)
                self.filePath = filename
                self.loadVideoCacheByFilename(filename.replace('mkv', 'log'))
                self.loadFile(filename)
                self.filedock.setWindowTitle(f'File list {currIndex + 1}/{len(self.mVideoList)}')


    def fileitemDoubleClicked(self, item=None):
        currIndex = self.mVideoList.index(ustr(item.text()))
        fileWidgetItem = self.fileListWidget.item(currIndex)
        fileWidgetItem.setBackground(Qt.white)
        if currIndex < len(self.mVideoList):
            filename = self.mVideoList[currIndex]
            if filename:
                self.filePath = filename
                self.loadVideoCacheByFilename(filename.replace('mkv', 'log'))
                self.loadFile(filename)
                self.filedock.setWindowTitle(f'File list {currIndex + 1}/{len(self.mVideoList)}')

    # Add chris
    def btnstate(self, item= None):
        """ Function to handle difficult examples
        Update on each object """
        if not self.canvas.editing():
            return

        item = self.currentItem()
        if not item: # If not selected Item, take the first one
            item = self.labelList.item(self.labelList.count()-1)

        difficult = self.diffcButton.isChecked()

        try:
            shape = self.itemsToShapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.setDirty()
            else:  # User probably changed item visibility
                self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            # FIXME when use propagation there is no selectedShape. It has to be fixed
            shape = self.canvas.selectedShape
            if shape and shape in self.shapesToItems:
                self.shapesToItems[shape].setSelected(True)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def addLabel(self, shape):
        shape.paintLabel = self.displayLabelOption.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generateColorByText(shape.label))
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        if shape is None:
            # print('rm empty label')
            return
        item = self.shapesToItems.get(shape)
        if item:
            self.labelList.takeItem(self.labelList.row(item))
            del self.shapesToItems[shape]
            del self.itemsToShapes[item]

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:
                shape.addPoint(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generateColorByText(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generateColorByText(label)

            self.addLabel(shape)

        self.canvas.loadShapes(s)

    def format_shape(self, s):
        return dict(label=s.label,
                    line_color=s.line_color.getRgb(),
                    fill_color=s.fill_color.getRgb(),
                    points=[(p.x(), p.y()) for p in s.points],
                    # add chris
                    difficult=s.difficult)

    def saveLabels(self):
        if self.shapes is None:
            self.shapes = YoloCacheReader(classListPath=config.PREDEF_YOLO_CLASSES)
        if self.propagateLabelsFlag:
            return True
        shapes = [self.format_shape(shape) for shape in self.canvas.shapes]
        currIndex = self.video_cap.get_position()
        self.shapes[currIndex + 1] = shapes
        return True


    def dubSelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def copySelectedShape(self):
        self.canvas.copySelectedShape()

    def pasteShape(self):
        if self.canvas.lastBBox:
            self.addLabel(self.canvas.pasteShape())
            # fix copy and delete
            self.shapeSelectionChanged(True)
            self.setDirty()

    def openInEditor(self):
        subprocess.Popen([config.IMAGE_EDITOR, self.filePath])

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            self.canvas.selectShape(self.itemsToShapes[item])
            shape = self.itemsToShapes[item]
            # Add Chris
            self.diffcButton.setChecked(shape.difficult)

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generateColorByText(shape.label)
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.useDefaultLabelCheckbox.isChecked() or not self.defaultLabelTextLine.text():
            if len(self.labelHist) > 0:
                self.labelDialog = LabelDialog(
                    parent=self, listItem=self.labelHist)

            # Sync single class mode from PR#106
            if self.singleClassMode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.labelDialog.popUp(text=self.prevLabelText)
                self.lastLabel = text
        else:
            text = self.defaultLabelTextLine.text()

        # Add Chris
        self.diffcButton.setChecked(False)
        if text is not None:
            self.prevLabelText = text
            generate_color = generateColorByText(text)
            shape = self.canvas.setLastLabel(text, generate_color, generate_color)
            self.addLabel(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.create.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if text not in self.labelHist:
                self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scrollBars[Qt.Horizontal]
        v_bar = self.scrollBars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scrollArea.width()
        h = self.scrollArea.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = h_bar.value() + move_x * d_h_bar_max
        new_v_bar_value = v_bar.value() + move_y * d_v_bar_max

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)
        mtime = QTime(0, 0, 0, 0)
        mtime = mtime.addMSecs(duration)
        self.elbl.setText(f"{mtime.toString()}|{self.video_cap.length(): >{8}}")

    def sliderPositionChanged(self):
        if self.video_cap:
            self.lbl.clear()
            mtime = QTime(0, 0, 0, 0)
            self.time = mtime.addMSecs(self.video_cap.get_time())
            self.lbl.setText(f"{self.time.toString()}|{self.video_cap.get_position() + 1: >{8}}")

    def loadFrame(self, position=0):

        frame_num = position + 1
        self.resetState()
        self.canvas.setEnabled(False)

        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if self.frameListWidget.count() > 0:

            # self.setListWidgetPosition(position)
            frameWidgetItem = self.frameListWidget.item(position)
            frameWidgetItem.setSelected(True)

            # Load image:
            # read data first and store for saving into label file.
            self.imageData = self.video_cap.get_frame(position)
            self.labelFile = None
            self.canvas.verified = False

            image = QImage.fromData(self.imageData)
            if image.isNull():
                return False
            self.image = image
            self.canvas.loadPixmap(QPixmap.fromImage(image))

            if self.propagateLabelsFlag:
                self.canvas.loadShapes(self.propagateLabels)
            else:
                if self.shapes:
                    self.loadLabels(self.shapes[frame_num])
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            # Label xml file and show bound box according to its filename
            # if self.usingPascalVocFormat is True:

            self.positionSlider.setSliderPosition(position)
            self.sliderPositionChanged()

            # Default : select last item if there is at least one item
            if self.labelList.count():
                self.labelList.setCurrentItem(self.labelList.item(self.labelList.count() - 1))
                self.labelList.item(self.labelList.count() - 1).setSelected(True)

            self.canvas.setFocus(True)
            return True
        return False

    def loadFile(self, filePath=None):
        """Load the specified file, or the last opened file if None."""

        # if self.shapes is not None:
        #     if not self.discardChangesDialog():
        #         return False

        if self.shapes is None:
            self.shapes = YoloCacheReader(classListPath=config.PREDEF_YOLO_CLASSES)
        self.resetState()
        self.canvas.setEnabled(False)
        if filePath is None:
            filePath = self.settings.get(SETTING_FILENAME)

        # Make sure that filePath is a regular python string, rather than QString
        filePath = ustr(filePath)

        unicodeFilePath = ustr(filePath)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicodeFilePath and self.frameListWidget.count() > 0:
            self.frameListWidget.clear()

        if unicodeFilePath and os.path.exists(unicodeFilePath):
            if LabelFile.isLabelFile(unicodeFilePath):
                try:
                    self.labelFile = LabelFile(unicodeFilePath)
                except LabelFileError as e:
                    self.errorMessage(u'Error opening file',
                                      (u"<p><b>%s</b></p>"
                                       u"<p>Make sure <i>%s</i> is a valid label file.")
                                      % (e, unicodeFilePath))
                    self.status("Error reading %s" % unicodeFilePath)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
                self.canvas.verified = self.labelFile.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                currIndex = self.mVideoList.index(self.filePath)
                fileWidgetItem = self.fileListWidget.item(currIndex)

                fileWidgetItem.setSelected(True)

                self.video_cap = VideoCapture(unicodeFilePath)
                self.mFrameList = [i for i in range(1, self.video_cap.length() + 1)]
                self.durationChanged(self.video_cap.duration)
                self.positionSlider.setRange(0, self.video_cap.length() - 1)
                for imgPath in self.mFrameList:
                    item = QListWidgetItem(str(imgPath))
                    self.frameListWidget.addItem(item)
                self.labelFile = None
                self.canvas.verified = False

            self.status("Loaded %s" % os.path.basename(unicodeFilePath))
            self.filePath = unicodeFilePath


            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)

            self.loadFrame(position=POS)
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filePath)
            self.toggleActions(True)

            self.setWindowTitle(__appname__ + ' ' + filePath)

            # Default : select last item if there is at least one item
            if self.labelList.count():
                self.labelList.setCurrentItem(self.labelList.item(self.labelList.count()-1))
                self.labelList.item(self.labelList.count()-1).setSelected(True)

            self.canvas.setFocus(True)
            return True
        return False

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.scrollArea.width() - e
        h1 = self.scrollArea.height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir and os.path.exists(self.defaultSaveDir):
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ''

        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ''

        settings[SETTING_AUTO_SAVE] = self.autoSaving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.singleClassMode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.displayLabelOption.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.drawSquaresOption.isChecked()
        settings.save()

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower() for fmt in QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    path = ustr(os.path.abspath(relativePath))
                    images.append(path)
        images.sort(key=lambda f: int(''.join(filter(str.isdigit, f))))
        return images

    def videoLength(self):
        return self.video_cap.length()

    def changeSavedirDialog(self, _value=False):
        if self.defaultSaveDir is not None:
            path = ustr(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = ustr(QFileDialog.getExistingDirectory(self,
                                                       '%s - Save annotations to the directory' % __appname__, path,  QFileDialog.ShowDirsOnly
                                                       | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage('%s . Annotation will be saved to %s' %
                                     ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotationDialog(self, _value=False):
        if self.filePath is None:
            self.statusBar().showMessage('Please select image first')
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.filePath)) if self.filePath else '.'
        if self.usingPascalVocFormat:
            filters = "Open Annotation XML file (%s)" % ' '.join(['*.xml'])
            filename = ustr(QFileDialog.getOpenFileName(self,'%s - Choose a xml file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.loadPascalXMLByFilename(filename)
        if self.usingYoloFormat:
            filters = "Open Annotation TXT file (%s)" % ' '.join(['*.txt', '*.log'])
            filename = ustr(QFileDialog.getOpenFileName(self,'%s - Choose a TXT file' % __appname__, path, filters))
            if filename:
                if isinstance(filename, (tuple, list)):
                    filename = filename[0]
            self.loadVideoCacheByFilename(filename)

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filePath) if self.filePath else '.'

        targetDirPath = ustr(QFileDialog.getExistingDirectory(self,
                                                     '%s - Open Directory' % __appname__, defaultOpenDirPath,
                                                     QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        self.importDirImages(targetDirPath)

    def setListWidgetPosition(self, pos):
        item = self.frameListWidget.item(pos)
        item.setSelected(True)
        self.frameListWidget.scrollToItem(self.frameListWidget.item(pos), hint=QAbstractItemView.EnsureVisible)

    def importDirImages(self, dirpath):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.dirname = dirpath
        self.filePath = None
        self.frameListWidget.clear()
        self.mFrameList = self.video_cap.length()
        self.openNextImg()
        for imgPath in self.mFrameList:
            item = QListWidgetItem(imgPath)
            self.frameListWidget.addItem(item)

    def verifyImg(self, _value=False):
        currIndex = self.mVideoList.index(self.filePath)
        fileWidgetItem = self.fileListWidget.item(currIndex)
        fileWidgetItem.setSelected(True)
        fileWidgetItem.setBackground(Qt.green)
        self.saveAnnotation()

        # Proceding next image without dialog if having any label
        # if self.filePath is not None:
        #     try:
        #         self.labelFile.toggleVerify()
        #     except AttributeError:
        #         # If the labelling file does not exist yet, create if and
        #         # re-save it with the verified attribute.
        #         self.saveFile()
        #         if self.labelFile != None:
        #             self.labelFile.toggleVerify()
        #         else:
        #             return
        #
        #     self.canvas.verified = self.labelFile.verified
        #     self.paintCanvas()
        #     self.saveFile()

    def openPrevImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.dirty is True or self.propagateLabelsFlag is True:
                self.saveFile()

        if not self.mayContinue():
            return

        if len(self.mFrameList) <= 0:
            return

        currIndex = self.video_cap.get_position()
        if 0 <= currIndex - 1 < len(self.mFrameList):
            currIndex = currIndex - 1
            self.frameListWidget.scrollToItem(self.frameListWidget.item(currIndex), hint=QAbstractItemView.EnsureVisible)
            self.loadFrame(currIndex)

    def openNextImg(self, _value=False):
        # Proceding prev image without dialog if having any label
        if self.autoSaving.isChecked():
            if self.dirty is True or self.propagateLabelsFlag is True:
                self.saveFile()

        if not self.mayContinue():
            return

        if len(self.mFrameList) <= 0:
            return

        currIndex = self.video_cap.get_position()
        if currIndex + 1 < len(self.mFrameList):
            currIndex = currIndex + 1
            self.frameListWidget.scrollToItem(self.frameListWidget.item(currIndex), hint=QAbstractItemView.EnsureVisible)

        if currIndex:
            self.loadFrame(currIndex)

    def jumpForward(self, n):
        if self.autoSaving.isChecked():
            if self.dirty is True or self.propagateLabelsFlag is True:
                self.saveFile()

        if not self.mayContinue():
            return

        if len(self.mFrameList) <= 0:
            return

        currIndex = self.video_cap.get_position()
        if currIndex + n < len(self.mFrameList):
            currIndex = currIndex + n
        else:
            currIndex = len(self.mFrameList) - 1
        self.frameListWidget.scrollToItem(self.frameListWidget.item(currIndex), hint=QAbstractItemView.EnsureVisible)

        if currIndex:
            self.loadFrame(currIndex)

    def jumpBackward(self, n):
        if self.autoSaving.isChecked():
            if self.dirty is True or self.propagateLabelsFlag is True:
                self.saveFile()

        if not self.mayContinue():
            return

        if len(self.mFrameList) <= 0:
            return

        currIndex = self.video_cap.get_position()
        if currIndex - n < len(self.mFrameList):
            currIndex = currIndex - n if currIndex - n >= 0 else 0
            self.frameListWidget.scrollToItem(self.frameListWidget.item(currIndex), hint=QAbstractItemView.EnsureVisible)
        self.loadFrame(currIndex)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return None
        path = os.path.dirname(str(self.filePath)) if self.filePath else '.'
        formats = ['*.mkv', '*.avi', '*.mkv', '*.ts', '*.mpeg', '*.mov']
        filters = "Video files (%s)" % ' '.join(formats + ['*%s' % CACHE_EXT])
        filename = QFileDialog.getOpenFileName(self, '%s - Choose Image or Label file' % __appname__, path, filters)
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.loadFile(filename)

    def saveFile(self, _value=False):
        if self.filePath:
            self._saveAnno()

        # if self.defaultSaveDir is not None and len(ustr(self.defaultSaveDir)):
        #     if self.filePath:
        #         imgFileName = os.path.basename(self.filePath)
        #         savedFileName = os.path.splitext(imgFileName)[0]
        #         savedPath = os.path.join(ustr(self.defaultSaveDir), savedFileName)
        #         self._saveFile(savedPath)
        # else:
        #     imgFileDir = os.path.dirname(self.filePath)
        #     imgFileName = os.path.basename(self.filePath)
        #     savedFileName = os.path.splitext(imgFileName)[0]
        #     savedPath = os.path.join(imgFileDir, savedFileName)
        #     self._saveFile(savedPath if self.labelFile
        #                    else self.saveFileDialog(removeExt=False))

    def saveAnnotation(self):
        self.saveFile()
        if not self.annoFilePath:
            head, ext = self.filePath.rsplit('.', maxsplit=1)
            self.annoFilePath = head + f'.anno'
            print()
        if self.annoFilePath and self.filePath:
            if self.shapes:
                self.shapes.save(filepath=self.annoFilePath)
        else:
            self.saveAnnotationAs()

    def saveAnnotationAs(self):
        if not self.filePath:
            self.errorMessage("You have to open video file before", "")
            self.status("Error saving annotation")
            return False
        file = self.saveFileDialog(removeExt=False)
        if file:
            self.annoFilePath = file
            if self.shapes:
                self.shapes.save(filepath=file)
            else:
                try:
                    with open(file, 'w') as inf:
                        pass
                except Exception as err:
                    self.errorMessage(str(type(err).__name__), str(err))
        return True

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveAnno(self.saveFileDialog())

    def saveFileDialog(self, removeExt=True):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % CACHE_EXT
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix('*.log')
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filenameWithoutExtension = os.path.splitext(self.filePath)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            fullFilePath = ustr(dlg.selectedFiles()[0])
            if removeExt:
                return os.path.splitext(fullFilePath)[0] # Return file path without the extension.
            else:
                return fullFilePath
        return ''

    def _saveAnno(self):
        if self.saveLabels():
            self.setClean()
            # self.statusBar().showMessage('Saved to  %s' % annotationFilePath)
            self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAnnoAs.setEnabled(False)

    def resetAll(self):
        self.settings.reset()
        self.close()
        proc = QProcess()
        proc.startDetached(os.path.abspath(__file__))

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(self.filePath) if self.filePath else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            Shape.line_color = color
            self.canvas.setDrawingColor(color)
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        self.remLabel(self.canvas.deleteSelected())
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def loadPredefinedClasses(self, predefClassesFile):
        if os.path.exists(predefClassesFile) is True:
            with codecs.open(predefClassesFile, 'r', 'utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.labelHist = [line]
                    else:
                        self.labelHist.append(line)

    def loadPascalXMLByFilename(self, xmlPath):
        if self.filePath is None:
            return
        if os.path.isfile(xmlPath) is False:
            return

        self.set_format(FORMAT_PASCALVOC)

        tVocParseReader = PascalVocReader(xmlPath)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.canvas.verified = tVocParseReader.verified

    def loadYOLOTXTByFilename(self, txtPath):
        if self.filePath is None:
            return
        if os.path.isfile(txtPath) is False:
            return

        self.set_format(FORMAT_YOLO)
        tYoloParseReader = YoloReader(txtPath, self.image, classListPath=defaultPrefdefClassFile())
        shapes = tYoloParseReader.getShapes()
        print (shapes)
        self.loadLabels(shapes)
        self.canvas.verified = tYoloParseReader.verified

    def loadVideoCacheByFilename(self, path):
        if self.filePath is None:
            return
        if os.path.isfile(path) is False:
            return

        p = pathlib.Path(path)
        if p.with_suffix('.anno').exists():
            path = str(p.with_suffix('.anno'))

        self.annoFilePath = str(pathlib.Path(path).with_suffix('.anno'))
        self.set_format(FORMAT_YOLO)
        tYoloParseReader = YoloCacheReader(path, classListPath=defaultPrefdefClassFile())
        self.shapes = tYoloParseReader
        self.loadLabels(tYoloParseReader[0])
        self.canvas.verified = tYoloParseReader.verified

    def togglePaintLabelsOption(self):
        for shape in self.canvas.shapes:
            shape.paintLabel = self.displayLabelOption.isChecked()

    def toogleDrawSquare(self):
        self.canvas.setDrawingShapeToSquare(self.drawSquaresOption.isChecked())


def defaultPrefdefClassFile():
    return config.PREDEF_YOLO_CLASSES

def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def get_main_app(argv=[]):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    # Usage : labelImg.py image predefClassFile saveDir
    win = MainWindow(argv[1] if len(argv) >= 2 else None,
                     argv[2] if len(argv) >= 3 else config.PREDEF_YOLO_CLASSES,
                     argv[3] if len(argv) >= 4 else None)
    win.show()
    return app, win


def main():
    '''construct main app and run it'''
    app, _win = get_main_app(sys.argv)
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main())
