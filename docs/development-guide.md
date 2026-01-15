# POD AI Studio 开发指南

## 目录

1. [环境搭建](#环境搭建)
2. [项目初始化](#项目初始化)
3. [开发流程](#开发流程)
4. [代码规范](#代码规范)
5. [组件开发指南](#组件开发指南)
6. [状态管理](#状态管理)
7. [API集成](#api集成)
8. [测试指南](#测试指南)
9. [部署流程](#部署流程)
10. [常见问题](#常见问题)

## 环境搭建

### 系统要求

- **操作系统**: Windows 10+, macOS 10.15+, Ubuntu 18.04+
- **Node.js**: >= 16.0.0 (推荐使用 LTS 版本)
- **npm**: >= 8.0.0 或 **yarn**: >= 1.22.0
- **Git**: >= 2.20.0

### 开发工具推荐

- **IDE**: Visual Studio Code
- **浏览器**: Chrome (最新版本)
- **扩展插件**:
  - ES7+ React/Redux/React-Native snippets
  - TypeScript Importer
  - Prettier - Code formatter
  - ESLint
  - Auto Rename Tag

### 环境安装

1. **安装Node.js**:
   ```bash
   # 使用nvm安装Node.js (推荐)
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   nvm install 18
   nvm use 18
   ```

2. **安装yarn (可选)**:
   ```bash
   npm install -g yarn
   ```

3. **验证安装**:
   ```bash
   node -v
   npm -v
   # 或
   yarn -v
   ```

## 项目初始化

### 克隆项目

```bash
git clone [repository-url]
cd podi-design-web
```

### 安装依赖

```bash
# 使用npm
npm install

# 或使用yarn
yarn install
```

### 环境变量配置

在项目根目录创建 `.env.local` 文件:

```env
# API / 认证统一入口
VITE_API_BASE_URL=http://localhost:8099/api

# 其他环境变量...
```

### 启动开发服务器

```bash
# 使用npm
npm run dev

# 或使用yarn
yarn dev
```

应用将在 `http://localhost:8080` 启动。

## 开发流程

### Git工作流

我们采用 **Git Flow** 工作流:

1. **主分支**: `main` - 生产环境代码
2. **开发分支**: `develop` - 开发环境代码
3. **功能分支**: `feature/功能名称` - 开发新功能
4. **修复分支**: `hotfix/问题描述` - 紧急修复
5. **发布分支**: `release/版本号` - 准备发布版本

### 分支操作示例

```bash
# 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/new-ai-tool

# 开发完成后提交
git add .
git commit -m "feat: 添加新的AI图像处理工具"
git push origin feature/new-ai-tool

# 创建Pull Request
# 在GitHub/GitLab上创建PR，从feature分支合并到develop分支
```

### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范:

```
<类型>[可选的作用域]: <描述>

[可选的正文]

[可选的脚注]
```

**类型**:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式化
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

**示例**:
```
feat(ai-tools): 添加图像无损放大功能

- 实现图片上传和预览
- 添加放大倍数选择
- 集成任务状态监控

Closes #123
```

## 代码规范

### TypeScript规范

1. **使用类型注解**:
   ```typescript
   // 好的做法
   interface UserData {
     id: string;
     name: string;
     email: string;
   }
   
   const getUserData = async (id: string): Promise<UserData> => {
     // 实现...
   };
   
   // 避免使用any
   const processData = (data: unknown): void => {
     // 实现类型检查后再处理
   };
   ```

2. **接口命名**:
   ```typescript
   // 组件Props接口
   interface ButtonProps {
     text: string;
     onClick: () => void;
   }
   
   // 数据模型接口
   interface TaskModel {
     id: string;
     status: TaskStatus;
   }
   ```

### React组件规范

1. **函数组件**:
   ```typescript
   // 使用函数式组件和Hooks
   import React, { useState, useEffect } from 'react';
   
   interface MyComponentProps {
     title: string;
     onAction?: () => void;
   }
   
   const MyComponent: React.FC<MyComponentProps> = ({ title, onAction }) => {
     const [state, setState] = useState<string>('');
     
     useEffect(() => {
       // 副作用处理
     }, []);
     
     return (
       <div>
         <h1>{title}</h1>
       </div>
     );
   };
   
   export default MyComponent;
   ```

2. **自定义Hooks**:
   ```typescript
   // 自定义Hook命名以use开头
   const useTaskManager = (initialTasks: Task[] = []) => {
     const [tasks, setTasks] = useState<Task[]>(initialTasks);
     
     const addTask = useCallback((task: Task) => {
       setTasks(prev => [...prev, task]);
     }, []);
     
     return { tasks, addTask };
   };
   ```

### CSS/样式规范

1. **Tailwind CSS**:
   ```tsx
   // 优先使用Tailwind类
   <div className="flex items-center justify-between p-4 bg-white rounded-lg shadow-md">
     <h2 className="text-lg font-semibold text-gray-800">标题</h2>
     <button className="px-4 py-2 text-white bg-blue-500 rounded hover:bg-blue-600">
       按钮
     </button>
   </div>
   ```

2. **条件样式**:
   ```tsx
   // 使用clsx或类名拼接
   import clsx from 'clsx';
   
   <div className={clsx(
     'base-class',
     {
       'active-class': isActive,
       'disabled-class': isDisabled
     }
   )}>
     内容
   </div>
   ```

## 组件开发指南

### 创建新组件

1. **组件文件结构**:
   ```
   components/
   └── MyComponent/
       ├── index.ts          # 导出文件
       ├── MyComponent.tsx   # 组件实现
       ├── MyComponent.test.tsx # 测试文件
       └── MyComponent.stories.tsx # Storybook故事(可选)
   ```

2. **组件模板**:
   ```typescript
   // MyComponent.tsx
   import React from 'react';
   import { Button } from '../ui/button';
   
   export interface MyComponentProps {
     title: string;
     onSubmit?: (data: any) => void;
     disabled?: boolean;
   }
   
   export const MyComponent: React.FC<MyComponentProps> = ({
     title,
     onSubmit,
     disabled = false
   }) => {
     const handleSubmit = () => {
       if (onSubmit) {
         onSubmit({ /* 数据 */ });
       }
     };
     
     return (
       <div className="p-4 border rounded-lg">
         <h2 className="text-xl font-bold mb-4">{title}</h2>
         <Button onClick={handleSubmit} disabled={disabled}>
           提交
         </Button>
       </div>
     );
   };
   
   export default MyComponent;
   ```

3. **组件导出**:
   ```typescript
   // index.ts
   export { MyComponent, type MyComponentProps } from './MyComponent';
   export default MyComponent;
   ```

### AI工具组件开发

每个AI工具组件应遵循统一的设计模式:

```typescript
// ExampleProcessor.tsx
import React, { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { ImageUploadZone } from '../ImageUploadZone';
import { TaskProgress } from '../TaskProgress';

export interface ExampleProcessorProps {
  action: string;
}

export const ExampleProcessor: React.FC<ExampleProcessorProps> = ({ action }) => {
  // 状态管理
  const [images, setImages] = useState<ImageData[]>([]);
  const [params, setParams] = useState<Record<string, any>>({});
  const [taskId, setTaskId] = useState<string>('');
  const [status, setStatus] = useState<TaskStatus>('idle');
  
  // 图片上传处理
  const handleImagesChange = useCallback((newImages: ImageData[]) => {
    setImages(newImages);
  }, []);
  
  // 参数变更处理
  const handleParamChange = useCallback((key: string, value: any) => {
    setParams(prev => ({ ...prev, [key]: value }));
  }, []);
  
  // 任务提交处理
  const handleSubmit = useCallback(async () => {
    if (images.length === 0) return;
    
    try {
      setStatus('processing');
      const taskId = await submitTask({
        action,
        images,
        params
      });
      setTaskId(taskId);
      
      // 启动任务监控
      startTaskMonitoring(taskId, (newStatus) => {
        setStatus(newStatus);
      });
    } catch (error) {
      console.error('任务提交失败:', error);
      setStatus('failed');
    }
  }, [action, images, params]);
  
  // 渲染参数配置UI
  const renderParamsConfig = () => (
    <div className="space-y-4">
      {/* 参数配置表单 */}
    </div>
  );
  
  return (
    <div className="container mx-auto p-4">
      <Card>
        <CardHeader>
          <CardTitle>示例AI工具</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 图片上传区域 */}
          <ImageUploadZone
            images={images}
            onChange={handleImagesChange}
            maxImages={1}
          />
          
          {/* 参数配置区域 */}
          {renderParamsConfig()}
          
          {/* 任务提交按钮 */}
          <Button 
            onClick={handleSubmit} 
            disabled={images.length === 0 || status === 'processing'}
            className="w-full"
          >
            {status === 'processing' ? '处理中...' : '开始处理'}
          </Button>
          
          {/* 任务进度显示 */}
          {taskId && (
            <TaskProgress taskId={taskId} status={status} />
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ExampleProcessor;
```

## 状态管理

### 认证状态

使用React Context管理全局认证状态:

```typescript
// contexts/AuthContext.tsx
import React, { createContext, useContext, useReducer, useEffect } from 'react';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

type AuthAction = 
  | { type: 'AUTH_START' }
  | { type: 'AUTH_SUCCESS'; payload: User }
  | { type: 'AUTH_FAILURE' }
  | { type: 'LOGOUT' };

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case 'AUTH_START':
      return { ...state, isLoading: true };
    case 'AUTH_SUCCESS':
      return { 
        ...state, 
        user: action.payload, 
        isAuthenticated: true, 
        isLoading: false 
      };
    case 'AUTH_FAILURE':
      return { 
        ...state, 
        user: null, 
        isAuthenticated: false, 
        isLoading: false 
      };
    case 'LOGOUT':
      return { 
        ...state, 
        user: null, 
        isAuthenticated: false, 
        isLoading: false 
      };
    default:
      return state;
  }
};

const AuthContext = createContext<AuthState & {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
} | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, {
    user: null,
    isLoading: true,
    isAuthenticated: false
  });
  
  // 登录方法
  const login = async (credentials: LoginCredentials) => {
    dispatch({ type: 'AUTH_START' });
    try {
      const user = await userAPI.login(credentials);
      localStorage.setItem('token', user.token);
      dispatch({ type: 'AUTH_SUCCESS', payload: user });
    } catch (error) {
      dispatch({ type: 'AUTH_FAILURE' });
      throw error;
    }
  };
  
  // 登出方法
  const logout = () => {
    localStorage.removeItem('token');
    dispatch({ type: 'LOGOUT' });
  };
  
  // 检查认证状态
  const checkAuth = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const user = await userAPI.getCurrentUser();
        dispatch({ type: 'AUTH_SUCCESS', payload: user });
      } catch (error) {
        localStorage.removeItem('token');
        dispatch({ type: 'AUTH_FAILURE' });
      }
    } else {
      dispatch({ type: 'AUTH_FAILURE' });
    }
  };
  
  useEffect(() => {
    checkAuth();
  }, []);
  
  return (
    <AuthContext.Provider value={{ ...state, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

### 任务状态管理

使用自定义Hook管理任务状态:

```typescript
// hooks/useTaskManager.ts
import { useState, useCallback, useEffect } from 'react';
import { taskManager } from '../utils/taskManager';

export const useTaskManager = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // 获取任务列表
  const fetchTasks = useCallback(async () => {
    setIsLoading(true);
    try {
      const taskList = await taskManager.getTasks();
      setTasks(taskList);
    } catch (error) {
      console.error('获取任务列表失败:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // 添加任务
  const addTask = useCallback(async (taskData: CreateTaskData) => {
    try {
      const newTask = await taskManager.createTask(taskData);
      setTasks(prev => [newTask, ...prev]);
      return newTask;
    } catch (error) {
      console.error('创建任务失败:', error);
      throw error;
    }
  }, []);
  
  // 更新任务状态
  const updateTaskStatus = useCallback((taskId: string, status: TaskStatus) => {
    setTasks(prev => prev.map(task => 
      task.id === taskId ? { ...task, status } : task
    ));
  }, []);
  
  // 删除任务
  const removeTask = useCallback((taskId: string) => {
    setTasks(prev => prev.filter(task => task.id !== taskId));
  }, []);
  
  // 初始化加载任务
  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);
  
  return {
    tasks,
    isLoading,
    fetchTasks,
    addTask,
    updateTaskStatus,
    removeTask
  };
};
```

## API集成

### HTTP工具类

项目使用自定义的HTTP工具类处理API请求:

```typescript
// utils/http.ts
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

class HttpClient {
  private client: AxiosInstance;
  
  constructor() {
    this.client = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8099/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    // 请求拦截器
    this.client.interceptors.request.use(
      (config) => {
        // 添加认证token
        const token = localStorage.getItem('token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // 处理认证错误
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }
  
  // GET请求
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.get(url, config);
  }
  
  // POST请求
  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.post(url, data, config);
  }
  
  // PUT请求
  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.put(url, data, config);
  }
  
  // DELETE请求
  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    return this.client.delete(url, config);
  }
}

export const http = new HttpClient();
```

### API服务封装

统一能力接口为前后端共享的唯一入口。常用模式：先读取 `/api/abilities` 渲染表单 → 调用 `POST /api/abilities/{abilityId}/invoke`（同步）或 `POST /api/ability-tasks`（异步）。示例：

```typescript
// services/abilityService.ts
import { http } from '../utils/http';

export interface AbilityInvokePayload {
  inputs: Record<string, any>;
  imageUrl?: string;
  imageBase64?: string;
  images?: { name: string; ossUrl: string }[];
  executorId?: string;
  metadata?: Record<string, any>;
  callbackUrl?: string;
}

export interface AbilityInvokeResponse {
  abilityId: string;
  status: 'succeeded' | 'failed';
  requestId: string;
  logId: number;
  durationMs: number;
  images?: { ossUrl: string; sourceUrl?: string }[];
  videos?: { ossUrl: string }[];
  texts?: string[];
  metadata?: Record<string, any>;
  raw?: Record<string, any>;
}

export interface AbilityTask {
  id: string;
  abilityId: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  logId?: number;
  durationMs?: number;
  requestPayload?: any;
  resultPayload?: AbilityInvokeResponse;
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
}

export const abilityService = {
  listAbilities() {
    return http.get('/abilities');
  },

  invokeAbility(abilityId: string, payload: AbilityInvokePayload) {
    return http.post<AbilityInvokeResponse>(`/abilities/${abilityId}/invoke`, payload);
  },

  createAbilityTask(abilityId: string, payload: AbilityInvokePayload) {
    return http.post<AbilityTask>('/ability-tasks', {
      abilityId,
      ...payload,
    });
  },

  getAbilityTask(taskId: string) {
    return http.get<AbilityTask>(`/ability-tasks/${taskId}`);
  },
};
```

> 更多字段及回调/成本信息详见 `docs/api/abilities.md`。管理端在“统一能力接口”板块会提供可复制的 `curl` 示例与默认参数。

## 测试指南

### 单元测试

使用 Jest 和 React Testing Library 进行单元测试:

```typescript
// components/MyComponent.test.tsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('renders correctly with title', () => {
    render(<MyComponent title="Test Title" />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });
  
  it('calls onSubmit when button is clicked', () => {
    const mockOnSubmit = jest.fn();
    render(<MyComponent title="Test Title" onSubmit={mockOnSubmit} />);
    
    fireEvent.click(screen.getByRole('button'));
    expect(mockOnSubmit).toHaveBeenCalled();
  });
  
  it('disables button when disabled prop is true', () => {
    render(<MyComponent title="Test Title" disabled />);
    
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

### 组件测试

```typescript
// components/ImageUploadZone.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImageUploadZone } from './ImageUploadZone';

describe('ImageUploadZone', () => {
  it('renders upload area', () => {
    render(<ImageUploadZone images={[]} onChange={jest.fn()} />);
    expect(screen.getByText(/拖拽图片到此处/)).toBeInTheDocument();
  });
  
  it('calls onChange when files are added', async () => {
    const mockOnChange = jest.fn();
    render(<ImageUploadZone images={[]} onChange={mockOnChange} />);
    
    const fileInput = screen.getByLabelText(/上传图片/);
    const file = new File(['test'], 'test.png', { type: 'image/png' });
    
    fireEvent.change(fileInput, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(mockOnChange).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            name: 'test.png',
            type: 'image/png'
          })
        ])
      );
    });
  });
});
```

### 运行测试

```bash
# 运行所有测试
npm test

# 运行测试并生成覆盖率报告
npm run test:coverage

# 监听模式运行测试
npm run test:watch
```

## 部署流程

### 构建生产版本

```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

### Docker部署

项目包含Dockerfile，可以使用Docker部署:

```dockerfile
# Dockerfile
FROM node:18-alpine as builder

WORKDIR /app

# 复制package文件
COPY package*.json ./
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产环境
FROM nginx:alpine

# 复制构建结果
COPY --from=builder /app/build /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 构建和运行Docker容器

```bash
# 构建Docker镜像
docker build -t podi-design-web .

# 运行容器
docker run -d -p 80:80 --name podi-design-web-container podi-design-web
```

## 常见问题

### 开发环境问题

**Q: 启动开发服务器时端口被占用**
```bash
# 解决方案1: 使用不同端口
npm run dev -- --port 3000

# 解决方案2: 终止占用端口的进程
lsof -ti:8080 | xargs kill -9
```

**Q: 依赖安装失败**
```bash
# 清除缓存并重新安装
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### 开发问题

**Q: 组件不更新状态**
```typescript
// 确保使用useState的正确语法
const [state, setState] = useState(initialValue);

// 确保在事件处理程序中调用setState
const handleClick = () => {
  setState(prevState => ({ ...prevState, updatedField: newValue }));
};
```

**Q: API请求失败**
```typescript
// 检查网络请求和错误处理
try {
  const response = await http.get('/api/data');
  console.log(response.data);
} catch (error) {
  console.error('API请求失败:', error);
  // 检查error.response获取更多错误信息
}
```

### 性能问题

**Q: 页面加载慢**
```typescript
// 使用React.memo优化组件渲染
const MyComponent = React.memo(({ data }) => {
  return <div>{data.name}</div>;
});

// 使用useMemo缓存计算结果
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(data);
}, [data]);

// 使用useCallback缓存函数
const handleClick = useCallback(() => {
  doSomething(id);
}, [id]);
```

---

这份开发指南将帮助新团队成员快速上手项目开发，确保代码质量和开发效率。如有任何疑问或建议，请随时提出。
