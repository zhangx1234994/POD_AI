# 构建阶段
FROM node:18-alpine AS builder

WORKDIR /app

# 复制package文件
COPY package*.json ./
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制自定义nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 添加时区设置
RUN apk add --no-cache tzdata
ENV TZ=Asia/Shanghai

# 暴露端口
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]