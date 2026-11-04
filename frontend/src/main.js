import { mount } from 'svelte';
import App from './App.svelte';
import './style.css';
import './theme.css';
import './dashboard.css';

mount(App, { target: document.getElementById('app') });
