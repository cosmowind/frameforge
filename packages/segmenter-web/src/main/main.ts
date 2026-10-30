import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import path from 'path';
import fs from 'fs';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 768,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs'),
    },
    backgroundColor: '#F5F7FA',
    show: false,
  });

  // 开发环境加载 Vite 开发服务器
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产环境加载打包后的文件
    // __dirname 指向 dist/main/，HTML 在 dist/index.html
    const htmlPath = path.join(__dirname, '..', 'index.html');
    console.log('Loading HTML from:', htmlPath);
    mainWindow.loadFile(htmlPath);
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC 处理器
ipcMain.handle('select-video-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: '选择视频文件',
    filters: [
      { name: 'MP4 视频', extensions: ['mp4'] },
      { name: '所有文件', extensions: ['*'] }
    ],
    properties: ['openFile']
  });
  
  if (result.canceled) {
    return null;
  }
  
  return result.filePaths[0];
});

ipcMain.handle('select-metadata-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: '选择元数据文件',
    filters: [
      { name: 'JSON 文件', extensions: ['json'] },
      { name: '所有文件', extensions: ['*'] }
    ],
    properties: ['openFile']
  });
  
  if (result.canceled) {
    return null;
  }
  
  return result.filePaths[0];
});

ipcMain.handle('save-metadata-file', async (_event, data: string) => {
  const result = await dialog.showSaveDialog(mainWindow!, {
    title: '保存元数据文件',
    filters: [
      { name: 'JSON 文件', extensions: ['json'] }
    ],
    defaultPath: 'metadata.json'
  });
  
  if (result.canceled) {
    return null;
  }
  
  try {
    fs.writeFileSync(result.filePath!, data, 'utf8');
    return result.filePath;
  } catch (error) {
    console.error('保存文件失败:', error);
    throw error;
  }
});

ipcMain.handle('read-file', async (_event, filePath: string) => {
  try {
    const data = fs.readFileSync(filePath, 'utf8');
    return data;
  } catch (error) {
    console.error('读取文件失败:', error);
    throw error;
  }
});

ipcMain.handle('select-output-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    title: '选择输出目录',
    properties: ['openDirectory']
  });
  
  if (result.canceled) {
    return null;
  }
  
  return result.filePaths[0];
});

ipcMain.handle('extract-video-info', async (_event, videoPath: string) => {
  try {
    const stats = fs.statSync(videoPath);
    const filename = path.basename(videoPath);
    
    // 使用ffprobe获取视频信息
    const { execSync } = require('child_process');
    
    try {
      const command = `ffprobe -v quiet -print_format json -show_format -show_streams "${videoPath}"`;
      const output = execSync(command, { encoding: 'utf8', windowsHide: true });
      const probeData = JSON.parse(output);
      
      const videoStream = probeData.streams.find((s: any) => s.codec_type === 'video');
      const format = probeData.format;
      
      const videoInfo = {
        filename,
        path: videoPath,
        duration: parseFloat(format.duration) || 0,
        width: videoStream?.width || 1920,
        height: videoStream?.height || 1080,
        codec: videoStream?.codec_name || 'h264',
        bitrate: parseInt(format.bit_rate) || 5000000,
        size: stats.size
      };
      
      console.log('提取的视频信息:', videoInfo);
      return videoInfo;
    } catch (ffmpegError) {
      console.error('FFmpeg提取失败，使用默认值:', ffmpegError);
      return {
        filename,
        path: videoPath,
        duration: 0,
        width: 1920,
        height: 1080,
        codec: 'h264',
        bitrate: 5000000,
        size: stats.size
      };
    }
  } catch (error) {
    console.error('提取视频信息失败:', error);
    throw error;
  }
});

// 检查视频对应的分割方案文件是否存在
ipcMain.handle('check-segments-file', async (_event, videoPath: string) => {
  try {
    const videoDir = path.dirname(videoPath);
    const videoFileName = path.basename(videoPath, path.extname(videoPath));
    const resultFolderName = `${videoFileName}-result`;
    const resultFolderPath = path.join(videoDir, resultFolderName);
    const segmentsFileName = `${videoFileName}-segments.json`;
    const segmentsFilePath = path.join(resultFolderPath, segmentsFileName);
    
    if (fs.existsSync(segmentsFilePath)) {
      return segmentsFilePath;
    }
    
    return null;
  } catch (error) {
    console.error('检查分割方案文件失败:', error);
    return null;
  }
});

ipcMain.handle('rotate-video', async (_event, inputPath: string, angle: number, clockwise: boolean) => {
  console.log('旋转视频:', { inputPath, angle, clockwise });
  
  try {
    const inputFileName = path.basename(inputPath, path.extname(inputPath));
    const inputDir = path.dirname(inputPath);
    const outputFileName = `${inputFileName}_rotated_${angle}${clockwise ? 'cw' : 'ccw'}.mp4`;
    const outputPath = path.join(inputDir, outputFileName);
    
    const { execSync } = require('child_process');
    
    // 根据旋转角度和方向确定 FFmpeg 的 transpose 参数
    let transposeFilter = '';
    switch (angle) {
      case 90:
        transposeFilter = clockwise ? 'transpose=1' : 'transpose=2';
        break;
      case 180:
        // 180度旋转等同于先水平翻转再垂直翻转
        transposeFilter = 'hflip,vflip';
        break;
      case 270:
        transposeFilter = clockwise ? 'transpose=2' : 'transpose=1';
        break;
      default:
        throw new Error(`不支持的旋转角度: ${angle}`);
    }
    
    // 使用 FFmpeg 旋转视频，调整输出尺寸以避免黑边
    // 对于90度和270度旋转，宽高会互换
    // 对于180度旋转，宽高保持不变
    const command = `ffmpeg -i "${inputPath}" -vf "${transposeFilter}" -c:a copy -y "${outputPath}"`;
    
    console.log('执行FFmpeg旋转命令:', command);
    
    execSync(command, { 
      stdio: 'pipe',
      windowsHide: true 
    });
    
    return {
      success: true,
      outputFile: outputPath
    };
  } catch (error) {
    console.error('视频旋转失败:', error);
    return {
      success: false,
      error: (error as Error).message
    };
  }
});

ipcMain.handle('split-video', async (_event, inputPath: string, segments: any[], outputDir: string, metadata?: any) => {
  console.log('分割视频:', { inputPath, segments: segments.length, outputDir });
  
  try {
    const outputFiles: string[] = [];
    const errors: string[] = [];
    
    const inputFileName = path.basename(inputPath, path.extname(inputPath));
    const resultFolderName = `${inputFileName}-result`;
    const resultFolderPath = path.join(outputDir, resultFolderName);
    
    if (!fs.existsSync(resultFolderPath)) {
      fs.mkdirSync(resultFolderPath, { recursive: true });
      console.log('创建输出文件夹:', resultFolderPath);
    }
    
    if (metadata) {
      const metadataFileName = `${inputFileName}-segments.json`;
      const metadataPath = path.join(resultFolderPath, metadataFileName);
      try {
        fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), 'utf8');
        console.log('保存分割方案:', metadataPath);
      } catch (error) {
        console.error('保存分割方案失败:', error);
        errors.push('保存分割方案失败');
      }
    }
    
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      const outputFileName = `${inputFileName}-${segment.index}.mp4`;
      const outputPath = path.join(resultFolderPath, outputFileName);
      
      if (mainWindow) {
        mainWindow.webContents.send('split-progress', {
          currentSegment: i + 1,
          totalSegments: segments.length,
          percentage: Math.round(((i + 1) / segments.length) * 100),
          currentFile: outputFileName
        });
      }
      
      try {
        const { execSync } = require('child_process');
        
        const formatTime = (seconds: number) => {
          const hours = Math.floor(seconds / 3600);
          const minutes = Math.floor((seconds % 3600) / 60);
          const secs = seconds % 60;
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toFixed(3).padStart(6, '0')}`;
        };
        
        const startTime = formatTime(segment.startTime);
        const duration = formatTime(segment.duration);
        
        const command = `ffmpeg -i "${inputPath}" -ss ${startTime} -t ${duration} -c copy -y "${outputPath}"`;
        
        console.log('执行FFmpeg命令:', command);
        
        execSync(command, { 
          stdio: 'pipe',
          windowsHide: true 
        });
        
        outputFiles.push(outputPath);
      } catch (error) {
        console.error(`分割片段${segment.index}失败:`, error);
        errors.push(`片段${segment.index}分割失败: ${(error as Error).message}`);
      }
    }
    
    return {
      success: errors.length === 0,
      outputFiles,
      errors,
      outputFolder: resultFolderPath
    };
  } catch (error) {
    console.error('视频分割失败:', error);
    return {
      success: false,
      outputFiles: [],
      errors: [(error as Error).message]
    };
  }
});
