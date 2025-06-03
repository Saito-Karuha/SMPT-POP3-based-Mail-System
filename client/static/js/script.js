document.addEventListener('DOMContentLoaded', () => {
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
});
