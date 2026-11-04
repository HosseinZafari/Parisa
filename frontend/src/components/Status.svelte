<script>
  import { statuses } from '../lib/api';
  export let status;
</script>

<span class="status-badge {status}"><span></span>{statuses[status] || status}</span>
