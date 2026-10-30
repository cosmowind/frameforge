import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import path from 'path';
import fs from 'fs';

// 禁用GPU加速，解决某些Win10系统视频无法显示的问题
app.disableHardwareAcceleration();

// 添加命令行参数优化视频播放
app.commandLine.appendSwitch('enable-features', 'SharedArrayBuffer');
app.commandLine.appendSwitch('disable-features', 'HardwareMediaKeyHandling');

// 导入打包的 FFmpeg 和 FFprobe 路径
let ffmpegPath: string;
let ffprobePath: string;

try {
  // 开发环境或打包后都能正确获取路径
  ffmpegPath = require('@ffmpeg-installer/ffmpeg').path.replace('app.asar', 'app.asar.unpacked');
  ffprobePath = require('@ffprobe-installer/ffprobe').path.replace('app.asar', 'app.asar.unpacked');
  
  console.log('FFmpeg 路径:', ffmpegPath);
  console.log('FFprobe 路径:', ffprobePath);
  
  // 验证文件是否存在
  if (!fs.existsSync(ffmpegPath)) {
    console.error('FFmpeg 文件不存在:', ffmpegPath);
  }
  if (!fs.existsSync(ffprobePath)) {
    console.error('FFprobe 文件不存在:', ffprobePath);
  }
} catch (error) {
  console.error('加载 FFmpeg/FFprobe 失败:', error);
  // 使用默认路径作为后备
  ffmpegPath = 'ffmpeg';
  ffprobePath = 'ffprobe';
}

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
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: false,
      allowRunningInsecureContent: false,
    },
    backgroundColor: '#F5F7FA',
    show: false,
  });

  // 开发环境加载 Vite 开发服务器
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产环境加载打包后的文件
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
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

ipcMain.handle('save-metadata-file', async (event, data: string) => {
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

ipcMain.handle('read-file', async (event, filePath: string) => {
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

ipcMain.handle('extract-video-info', async (event, videoPath: string) => {
  // 使用FFmpeg提取视频信息
  try {
    const stats = fs.statSync(videoPath);
    const filename = path.basename(videoPath);
    
    // 使用ffprobe获取视频信息
    const { execSync } = require('child_process');
    
    try {
      // 使用打包的 ffprobe 获取视频信息（JSON格式）
      const command = `"${ffprobePath}" -v quiet -print_format json -show_format -show_streams "${videoPath}"`;
      const output = execSync(command, { encoding: 'utf8', windowsHide: true });
      const probeData = JSON.parse(output);
      
      // 提取视频流信息
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
      // 如果FFmpeg失败，返回基本信息
      return {
        filename,
        path: videoPath,
        duration: 0, // 无法获取时长
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

// 生成 H.264 预览文件（用于 HEVC 等不支持的编码）
ipcMain.handle('generate-preview', async (event, videoPath: string, duration: number) => {
  try {
    const videoDir = path.dirname(videoPath);
    const videoFileName = path.basename(videoPath, path.extname(videoPath));
    const previewPath = path.join(videoDir, `${videoFileName}_preview.mp4`);

    // 如果预览文件已存在，直接返回
    if (fs.existsSync(previewPath)) {
      console.log('预览文件已存在:', previewPath);
      return previewPath;
    }

    console.log('开始生成预览文件...');
    const { spawn } = require('child_process');

    return new Promise<string>((resolve, reject) => {
      const args = [
        '-i', videoPath,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-vf', 'scale=1280:-2',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-y', previewPath
      ];

      const proc = spawn(ffmpegPath, args, { windowsHide: true });
      let stderrBuf = '';

      proc.stderr.on('data', (data: Buffer) => {
        stderrBuf += data.toString();

        // 解析 FFmpeg 的 time=HH:MM:SS.xx 进度输出
        const matches = stderrBuf.match(/time=(\d+):(\d+):(\d+\.\d+)/g);
        if (matches && duration > 0) {
          const last = matches[matches.length - 1];
          const parts = last.match(/time=(\d+):(\d+):(\d+\.\d+)/);
          if (parts) {
            const elapsed = parseInt(parts[1]) * 3600 + parseInt(parts[2]) * 60 + parseFloat(parts[3]);
            const percent = Math.min(Math.round((elapsed / duration) * 100), 100);
            if (mainWindow) {
              mainWindow.webContents.send('preview-progress', percent);
            }
          }
        }
        
        // 检查是否有错误信息
        if (stderrBuf.includes('Error') || stderrBuf.includes('error')) {
          console.log('FFmpeg 警告:', stderrBuf.slice(-500)); // 打印最后500字符
        }
      });

      proc.on('close', (code: number) => {
        if (code === 0) {
          console.log('预览文件生成成功:', previewPath);
          resolve(previewPath);
        } else {
          console.error('FFmpeg 生成预览文件失败，退出码:', code);
          console.error('FFmpeg 错误输出:', stderrBuf.slice(-1000));
          reject(new Error(`FFmpeg exited with code ${code}. 错误信息: ${stderrBuf.slice(-500)}`));
        }
      });

      proc.on('error', reject);
    });
  } catch (error) {
    console.error('生成预览文件失败:', error);
    throw error;
  }
});

// 检查视频对应的分割方案文件是否存在
ipcMain.handle('check-segments-file', async (event, videoPath: string) => {
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

ipcMain.handle('split-video', async (event, inputPath: string, segments: any[], outputDir: string, metadata?: any) => {
  // FFmpeg视频分割实现
  console.log('分割视频:', { inputPath, segments: segments.length, outputDir });
  
  try {
    const outputFiles: string[] = [];
    const errors: string[] = [];
    
    // 获取输入文件名（不含扩展名）
    const inputFileName = path.basename(inputPath, path.extname(inputPath));
    
    // 创建以原视频名称命名的输出文件夹（加上-result后缀）
    const resultFolderName = `${inputFileName}-result`;
    const resultFolderPath = path.join(outputDir, resultFolderName);
    
    // 如果文件夹不存在，创建它
    if (!fs.existsSync(resultFolderPath)) {
      fs.mkdirSync(resultFolderPath, { recursive: true });
      console.log('创建输出文件夹:', resultFolderPath);
    }
    
    // 保存元数据到结果文件夹
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
    
    // 处理每个片段
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      const outputFileName = `${inputFileName}-${segment.index}.mp4`;
      const outputPath = path.join(resultFolderPath, outputFileName); // 使用新的文件夹路径
      
      // 发送进度更新
      if (mainWindow) {
        mainWindow.webContents.send('split-progress', {
          currentSegment: i + 1,
          totalSegments: segments.length,
          percentage: Math.round(((i + 1) / segments.length) * 100),
          currentFile: outputFileName
        });
      }
      
      try {
        // 使用child_process执行ffmpeg命令
        // 注意：需要系统安装ffmpeg
        const { execSync } = require('child_process');
        
        // 格式化时间为 HH:MM:SS.mmm
        const formatTime = (seconds: number) => {
          const hours = Math.floor(seconds / 3600);
          const minutes = Math.floor((seconds % 3600) / 60);
          const secs = seconds % 60;
          return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toFixed(3).padStart(6, '0')}`;
        };
        
        const startTime = formatTime(segment.startTime);
        const duration = formatTime(segment.duration);
        
        // FFmpeg命令：使用打包的 ffmpeg 和 -c copy保持原始质量
        const command = `"${ffmpegPath}" -i "${inputPath}" -ss ${startTime} -t ${duration} -c copy -y "${outputPath}"`;
        
        console.log('执行FFmpeg命令:', command);
        
        // 执行命令（同步执行以便按顺序处理）
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
      outputFolder: resultFolderPath // 返回输出文件夹路径
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
