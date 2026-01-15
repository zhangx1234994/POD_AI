// 验证轮询是否已被禁用的脚本
// 在浏览器控制台中运行此脚本

console.log('=== 验证轮询是否已被禁用 ===');

// 检查全局禁用状态
try {
  if (window.smartPollingManager && window.SmartPollingManager) {
    console.log('1. 全局禁用状态:', SmartPollingManager.isGloballyDisabled());
    console.log('2. 是否已初始化:', smartPollingManager.isInitialized());
    console.log('3. 当前轮询状态:', smartPollingManager.getPollingStatus());
    
    // 尝试初始化轮询
    smartPollingManager.initialize(() => {
      console.log('轮询回调执行');
    });
    console.log('4. 初始化尝试后的状态:', smartPollingManager.isInitialized());
    
    // 尝试启动轮询
    smartPollingManager.startPolling();
    console.log('5. 启动尝试后的轮询状态:', smartPollingManager.getPollingStatus());
    
    // 检查是否有定时器
    console.log('6. 检查是否有定时器运行...');
    let timerCount = 0;
    for (let i = 1; i < 10000; i++) {
      if (window.setTimeout.toString().includes(`setTimeout(${i}`)) {
        timerCount++;
      }
    }
    console.log('定时器数量（大约）:', timerCount);
    
    // 最终结论
    if (SmartPollingManager.isGloballyDisabled() && 
        !smartPollingManager.isInitialized() && 
        smartPollingManager.getPollingStatus() === 'idle') {
      console.log('✅ 轮询已成功禁用');
    } else {
      console.log('❌ 轮询可能未完全禁用');
    }
  } else {
    console.log('❌ 无法访问智能轮询管理器，可能页面未完全加载');
  }
} catch (error) {
  console.error('验证过程中出错:', error);
}

console.log('=== 验证完成 ===');