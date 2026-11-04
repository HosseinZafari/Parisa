<script>
  export let name = 'grid';
  export let size = 20;
  export let stroke = 1.7;
  const paths = {
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    orders: 'M8 4H5v17h14V4h-3 M9 2h6v5H9z M8 12h8 M8 16h5',
    chat: 'M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5A8.5 8.5 0 0 1 10.5 3h2a8.5 8.5 0 0 1 8.5 8.5Z M7 11h10 M7 15h6',
    box: 'm3 7 9-5 9 5v10l-9 5-9-5V7Z m0 0 9 5 9-5 M12 12v10 M7.5 4.5l9 5v4',
    people:
      'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
    bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',
    settings:
      'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3l-1 3-3 1-2 3 2 3-1 3 3 3 3-1 3 2 3-2 3 1 2-3-1-3 2-3-2-3-3-1-1-3H9Z',
    plus: 'M12 5v14 M5 12h14',
    search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
    arrow: 'M19 12H5 m6-6-6 6 6 6',
    chevron: 'm15 18-6-6 6-6',
    down: 'm6 9 6 6 6-6',
    check: 'm5 12 4 4L19 6',
    clock: 'M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
    calendar: 'M4 5h16v16H4z M16 3v4 M8 3v4 M4 11h16',
    wallet: 'M20 8V5H4a2 2 0 0 1 0-4h14v4 M4 5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16V8H4 M16 12h6v5h-6z',
    trend: 'm3 17 6-6 4 4 8-10 M15 5h6v6',
    alert: 'm12 3 10 18H2L12 3Z M12 9v5 M12 17v.1',
    send: 'm22 2-7 20-4-9-9-4L22 2Z M11 13 22 2',
    truck:
      'M1 3h14v14H1z M15 8h4l3 4v5h-7 M5 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4 M18 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4',
    leaf: 'M20 3C9 1 2 8 5 16c7 8 17 0 15-13Z M4 21 15 10',
    instagram:
      'M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5Z M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z M17.5 6.5h.01',
    logout: 'M9 21H3V3h6 M12 12h10 m-5-5 5 5-5 5',
    close: 'm6 6 12 12 M6 18 18 6',
    more: 'M5 12h.01 M12 12h.01 M19 12h.01',
    edit: 'm16 3 5 5-12 12-6 1 1-6L16 3Z M14 5l5 5',
    link: 'm10 13 4-4 M8 15l-2 2a3 3 0 0 1-4-4l5-5a3 3 0 0 1 4 0 M16 9l2-2a3 3 0 0 1 4 4l-5 5a3 3 0 0 1-4 0',
    lock: 'M5 10h14v11H5z M8 10V6a4 4 0 0 1 8 0v4',
    help: 'M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3 M12 17h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
    candle: 'M7 10h10v12H7z M12 10V7 M12 7c-4-2-1-5 0-6 3 3 3 5 0 6Z',
    flower: 'M12 12c-10-4-8-12-3-8 1-7 8-3 5 2 7-3 10 5 3 6 6 4 0 10-4 5-1 7-9 5-7-1-6 1-9-7-1-6Z M12 12v11',
    dress: 'M8 2h8l2 5-4 4 6 11H4l6-11-4-4 2-5Z M8 2c0 4 8 4 8 0 M10 11h4',
    art: 'M3 3h18v18H3z M3 16l5-5 5 5 4-4 4 4 M16 7h.01',
    cookie: 'M20 10a5 5 0 0 1-6-6C6-1-1 11 5 18s19 3 15-8Z M8 8h.01 M7 14h.01 M12 17h.01 M13 11h.01',
    filter: 'M3 5h18 M6 12h12 M9 19h6',
    refresh: 'M21 10a9 9 0 1 0-2 8 M21 3v7h-7',
    menu: 'M3 6h18 M3 12h18 M3 18h18',
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={stroke}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"><path d={paths[name] || paths.box} /></svg
>
