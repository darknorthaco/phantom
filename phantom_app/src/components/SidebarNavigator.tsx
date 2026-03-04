interface Props {
  active: string;
  onNavigate: (view: string) => void;
}

const NAV_SECTIONS = [
  {
    label: 'Operations',
    items: [
      { id: 'chat',        icon: '◎', name: 'Chat' },
      { id: 'console',     icon: '▸', name: 'Console' },
      { id: 'workers',     icon: '◈', name: 'Workers' },
      { id: 'routing',     icon: '⇄', name: 'Routing' },
      { id: 'tasks',       icon: '☰', name: 'Tasks' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { id: 'models',      icon: '◉', name: 'Models' },
      { id: 'ephemeral',   icon: '◌', name: 'Ephemeral' },
    ],
  },
  {
    label: 'Infrastructure',
    items: [
      { id: 'deployments', icon: '▣', name: 'Deployments' },
      { id: 'logs',        icon: '≡', name: 'Logs' },
      { id: 'settings',    icon: '⚙', name: 'Settings' },
    ],
  },
  {
    label: 'DevOps',
    items: [
      { id: 'experimental', icon: '⚡', name: 'Experimental' },
    ],
  },
];

export default function SidebarNavigator({ active, onNavigate }: Props) {
  return (
    <nav className="sidebar">
      {NAV_SECTIONS.map((section) => (
        <div key={section.label} className="sidebar-section">
          <div className="sidebar-label">{section.label}</div>
          {section.items.map((item) => (
            <div
              key={item.id}
              className={`sidebar-item ${active === item.id ? 'active' : ''}`}
              onClick={() => onNavigate(item.id)}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.name}</span>
            </div>
          ))}
        </div>
      ))}
    </nav>
  );
}
