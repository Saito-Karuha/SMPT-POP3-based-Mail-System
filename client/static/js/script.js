document.addEventListener('DOMContentLoaded', function() {
  // ===========================================
  // 邮件系统功能部分
  // ===========================================
  
  // -------------------
  // 邮件删除功能（收件箱 / 已发送 / 垃圾箱都可用）
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const tr = btn.closest('tr');
      if (!tr) return;
      const emailId = tr.dataset.id;
      if (!emailId) return;

      if (!confirm('确定要删除这封邮件吗？')) return;

      try {
        const response = await fetch(`/emails/${emailId}`, { method: 'DELETE' });
        if (response.ok) {
          tr.remove();
          alert('邮件已删除');
        } else {
          alert('删除失败');
        }
      } catch (err) {
        alert('删除出错: ' + err.message);
      }
    });
  });

  // -------------------
  // 搜索过滤功能（适用于邮件列表页面）
  const searchInput = document.querySelector('.search-box input');
  if (searchInput) {
    searchInput.addEventListener('keyup', () => {
      const term = searchInput.value.trim().toLowerCase();
      document.querySelectorAll('tbody tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
      });
    });
  }

  // -------------------
  // 撰写邮件页面异步发送功能
  const emailForm = document.querySelector('.compose-container form');
  if (emailForm) {
    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const formData = new FormData(emailForm);
      const submitBtn = emailForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = '发送中...';

      // 创建或清空日志显示区（用于显示详细错误日志）
      let logDiv = document.querySelector('.send-log');
      if (!logDiv) {
        logDiv = document.createElement('div');
        logDiv.className = 'send-log';
        logDiv.style.whiteSpace = 'pre-wrap';
        logDiv.style.marginTop = '10px';
        logDiv.style.color = 'red';
        emailForm.appendChild(logDiv);
      }
      logDiv.textContent = '';

      try {
        const response = await fetch(emailForm.action, {
          method: 'POST',
          body: formData,
        });

        const contentType = response.headers.get('Content-Type') || '';
        if (contentType.includes('application/json')) {
          const data = await response.json();
          if (data.success) {
            alert('邮件发送成功！');
            logDiv.textContent = '邮件发送成功。';
            submitBtn.disabled = false;
            submitBtn.textContent = '发送';
            // 可选：清空表单
            // emailForm.reset();
          } else {
            // 显示后端返回的详细错误日志
            logDiv.textContent = `[COMPOSE] 发送失败: ${data.message || '未知错误'}`;
            submitBtn.disabled = false;
            submitBtn.textContent = '发送';
          }
        } else {
          if (response.redirected) {
            alert('邮件发送成功，请刷新');
            submitBtn.disabled = false;
            submitBtn.textContent = '发送';
          } else {
            alert('邮件尝试发送完成，请刷新');
            submitBtn.disabled = false;
            submitBtn.textContent = '发送';
          }
        }
      } catch (err) {
        logDiv.textContent = '[COMPOSE] 发送邮件出错: ' + err.message;
        alert('发送邮件出错: ' + err.message);
        submitBtn.disabled = false;
        submitBtn.textContent = '发送';
      }
    });
  }

  // -------------------
  // 已发送和垃圾箱页面 — 恢复邮件功能（垃圾箱用）
  document.querySelectorAll('.btn-restore').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const tr = btn.closest('tr');
      const emailId = tr?.dataset.id;
      if (!emailId) return;

      if (!confirm('确定要恢复这封邮件吗？')) return;

      try {
        const response = await fetch(`/emails/${emailId}/restore`, { method: 'POST' });
        if (response.ok) {
          tr.remove();
          alert('邮件已恢复');
        } else {
          alert('恢复失败');
        }
      } catch (err) {
        alert('恢复出错: ' + err.message);
      }
    });
  });

  // -------------------
  // 垃圾箱永久删除邮件功能
  document.querySelectorAll('.btn-delete-permanent').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const tr = btn.closest('tr');
      const emailId = tr?.dataset.id;
      if (!emailId) return;

      if (!confirm('确定要永久删除这封邮件吗？此操作不可恢复！')) return;

      try {
        const response = await fetch(`/emails/${emailId}/delete_permanent`, { method: 'DELETE' });
        if (response.ok) {
          tr.remove();
          alert('邮件已永久删除');
        } else {
          alert('删除失败');
        }
      } catch (err) {
        alert('删除出错: ' + err.message);
      }
    });
  });

  // ===========================================
  // 增强的粒子背景效果部分 - 包含凝聚效果
  // ===========================================
  
  // 粒子背景效果
  const canvas = document.getElementById('particles');
  if (!canvas) return;
  
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  
  // 粒子数组
  const particles = [];
  const particleCount = window.innerWidth < 768 ? 80 : 120;
  
  // 鼠标位置和配置
  const mouse = {
      x: null,
      y: null,
      radius: 150, // 影响范围
      attractionForce: 0.05, // 吸引力强度
      repulsionRadius: 50, // 排斥半径
      repulsionForce: 0.8, // 排斥力强度
      isPressed: false // 鼠标是否按下
  };
  
  // 窗口大小调整
  window.addEventListener('resize', function() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
  });
  
  // 鼠标事件
  window.addEventListener('mousemove', function(event) {
      mouse.x = event.x;
      mouse.y = event.y;
  });
  
  window.addEventListener('mousedown', function() {
      mouse.isPressed = true;
  });
  
  window.addEventListener('mouseup', function() {
      mouse.isPressed = false;
  });
  
  // 增强的粒子类
  class Particle {
      constructor(x, y, directionX, directionY, size, color) {
          this.x = x;
          this.y = y;
          this.originalX = x; // 记录原始位置
          this.originalY = y;
          this.directionX = directionX;
          this.directionY = directionY;
          this.originalDirectionX = directionX; // 记录原始速度
          this.originalDirectionY = directionY;
          this.size = size;
          this.originalSize = size; // 记录原始大小
          this.color = color;
          this.opacity = 0.8;
          this.velocityX = 0; // 当前速度
          this.velocityY = 0;
          this.friction = 0.95; // 摩擦力
          this.maxSpeed = 3; // 最大速度限制
      }
      
      draw() {
          ctx.save();
          ctx.globalAlpha = this.opacity;
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
          ctx.fillStyle = this.color;
          ctx.fill();
          
          // 添加发光效果
          if (this.size > this.originalSize) {
              ctx.shadowBlur = 20;
              ctx.shadowColor = this.color;
              ctx.fill();
          }
          ctx.restore();
      }
      
      update() {
          // 检查画布边界
          if (this.x > canvas.width || this.x < 0) {
              this.directionX = -this.directionX;
          }
          if (this.y > canvas.height || this.y < 0) {
              this.directionY = -this.directionY;
          }
          
          // 计算与鼠标的距离
          if (mouse.x !== null && mouse.y !== null) {
              let dx = mouse.x - this.x;
              let dy = mouse.y - this.y;
              let distance = Math.sqrt(dx * dx + dy * dy);
              
              // 凝聚效果：鼠标按下或靠近时的吸引力
              if (distance < mouse.radius) {
                  let force = (mouse.radius - distance) / mouse.radius;
                  
                  if (mouse.isPressed || distance < mouse.radius * 0.6) {
                      // 强吸引力（鼠标按下或很近时）
                      let attractionX = (dx / distance) * force * mouse.attractionForce * 2;
                      let attractionY = (dy / distance) * force * mouse.attractionForce * 2;
                      
                      this.velocityX += attractionX;
                      this.velocityY += attractionY;
                      
                      // 增大粒子尺寸和亮度
                      this.size = this.originalSize * (1 + force * 0.5);
                      this.opacity = Math.min(1, 0.8 + force * 0.4);
                      
                      // 改变颜色强度
                      let intensity = Math.floor(100 + force * 100);
                      this.color = `rgba(${intensity}, ${intensity + 50}, 237, ${this.opacity})`;
                  } else {
                      // 轻微吸引力
                      let attractionX = (dx / distance) * force * mouse.attractionForce * 0.5;
                      let attractionY = (dy / distance) * force * mouse.attractionForce * 0.5;
                      
                      this.velocityX += attractionX;
                      this.velocityY += attractionY;
                  }
                  
                  // 近距离排斥效果（防止粒子重叠）
                  if (distance < mouse.repulsionRadius && distance > 0) {
                      let repulsionX = -(dx / distance) * mouse.repulsionForce;
                      let repulsionY = -(dy / distance) * mouse.repulsionForce;
                  }
              } else {
                  // 远离鼠标时恢复原状
                  this.size += (this.originalSize - this.size) * 0.1;
                  this.opacity += (0.8 - this.opacity) * 0.1;
                  this.color = 'rgba(100, 149, 237, 0.8)';
                  
                  // 轻微的回归原始轨迹的力
                  this.velocityX += (this.originalDirectionX - this.velocityX) * 0.02;
                  this.velocityY += (this.originalDirectionY - this.velocityY) * 0.02;
              }
          }
          
          // 应用摩擦力
          this.velocityX *= this.friction;
          this.velocityY *= this.friction;
          
          // 限制最大速度
          let speed = Math.sqrt(this.velocityX * this.velocityX + this.velocityY * this.velocityY);
          if (speed > this.maxSpeed) {
              this.velocityX = (this.velocityX / speed) * this.maxSpeed;
              this.velocityY = (this.velocityY / speed) * this.maxSpeed;
          }
          
          // 更新位置
          this.x += this.directionX + this.velocityX;
          this.y += this.directionY + this.velocityY;
          
          // 边界检查和反弹
          if (this.x <= this.size || this.x >= canvas.width - this.size) {
              this.directionX = -this.directionX;
              this.velocityX *= -0.5;
          }
          if (this.y <= this.size || this.y >= canvas.height - this.size) {
              this.directionY = -this.directionY;
              this.velocityY *= -0.5;
          }
          
          // 绘制粒子
          this.draw();
      }
  }
  
  // 创建粒子
  function init() {
      particles.length = 0;
      for (let i = 0; i < particleCount; i++) {
          let size = (Math.random() * 2) + 1;
          let x = Math.random() * (canvas.width - size * 2) + size;
          let y = Math.random() * (canvas.height - size * 2) + size;
          let directionX = (Math.random() * 0.8) - 0.4;
          let directionY = (Math.random() * 0.8) - 0.4;
          let color = 'rgba(100, 149, 237, 0.8)';
          
          particles.push(new Particle(x, y, directionX, directionY, size, color));
      }
  }
  
  // 动画循环
  function animate() {
      requestAnimationFrame(animate);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      for (let i = 0; i < particles.length; i++) {
          particles[i].update();
      }
      
      connect();
  }
  
  // 连接相近的粒子（增强版）
  function connect() {
      for (let a = 0; a < particles.length; a++) {
          for (let b = a + 1; b < particles.length; b++) {
              let dx = particles[a].x - particles[b].x;
              let dy = particles[a].y - particles[b].y;
              let distance = Math.sqrt(dx * dx + dy * dy);
              
              // 动态连接距离
              let maxDistance = 120;
              if (mouse.x !== null && mouse.y !== null) {
                  let mouseDistA = Math.sqrt((mouse.x - particles[a].x) ** 2 + (mouse.y - particles[a].y) ** 2);
                  let mouseDistB = Math.sqrt((mouse.x - particles[b].x) ** 2 + (mouse.y - particles[b].y) ** 2);
                  
                  // 如果粒子靠近鼠标，增加连接距离
                  if (mouseDistA < mouse.radius || mouseDistB < mouse.radius) {
                      maxDistance = 180;
                  }
              }
              
              if (distance < maxDistance) {
                  let opacity = 1 - (distance / maxDistance);
                  
                  // 根据粒子大小调整连线亮度
                  let avgSize = (particles[a].size + particles[b].size) / 2;
                  let sizeMultiplier = avgSize / particles[a].originalSize;
                  opacity *= sizeMultiplier;
                  
                  ctx.strokeStyle = `rgba(100, 149, 237, ${opacity * 0.6})`;
                  ctx.lineWidth = opacity * 2;
                  ctx.beginPath();
                  ctx.moveTo(particles[a].x, particles[a].y);
                  ctx.lineTo(particles[b].x, particles[b].y);
                  ctx.stroke();
              }
          }
      }
  }
  
  // 初始化并启动粒子动画
  init();
  animate();
});