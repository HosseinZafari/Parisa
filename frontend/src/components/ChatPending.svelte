<script>
  import Icon from './Icon.svelte';
  export let label = 'در حال آماده‌کردن پاسخ…';
</script>

<div class="response-pending" role="status" aria-live="polite" aria-atomic="true">
  <span class="pending-mark"><Icon name="leaf" size={17} /></span>
  <span class="pending-label">{label}</span>
  <span class="pending-dots" aria-hidden="true"><i></i><i></i><i></i></span>
</div>

<style>
  .response-pending {
    display: flex;
    align-items: center;
    gap: 10px;
    width: fit-content;
    max-width: 100%;
    margin: 18px 0 4px;
    padding: 11px 14px;
    border: 1px solid var(--line);
    border-radius: 14px 4px 14px 14px;
    color: var(--green);
    background: var(--mint);
  }
  .pending-mark {
    display: flex;
    opacity: 0.8;
  }
  .pending-label {
    font-size: 12px;
    line-height: 1.8;
  }
  .pending-dots {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-inline-start: 8px;
    flex-shrink: 0;
  }
  .pending-dots i {
    display: block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
    animation: breathe 1.3s ease-in-out infinite;
  }
  .pending-dots i:nth-child(2) {
    animation-delay: 0.16s;
  }
  .pending-dots i:nth-child(3) {
    animation-delay: 0.32s;
  }
  @keyframes breathe {
    0%,
    60%,
    100% {
      opacity: 0.3;
      transform: translateY(0);
    }
    30% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pending-dots i {
      animation: none;
      opacity: 0.65;
    }
  }
  @media (max-width: 700px) {
    .response-pending {
      gap: 8px;
      padding: 10px 12px;
    }
    .pending-label {
      font-size: 11px;
    }
  }
</style>
