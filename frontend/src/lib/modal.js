// گفتگوی بومی مرورگر: محدود کردن تمرکز، پشتیبانی Escape و بازگشت تمرکز.
export function modal(node) {
  const previous = document.activeElement;
  node.showModal();
  return {
    destroy() {
      node.close();
      if (previous instanceof HTMLElement) previous.focus();
    },
  };
}
