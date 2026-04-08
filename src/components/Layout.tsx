import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  HardDrive, 
  Ticket, 
  ShoppingCart, 
  Package, 
  GitBranch, 
  Scale, 
  BarChart3, 
  ShieldX, 
  History, 
  ShieldCheck, 
  Settings,
  LogOut,
  Bell,
  User,
  Menu,
  X
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/store/useAuthStore';
import { useNotifications } from '@/hooks/useNotifications';
import { Badge } from '@/components/ui/badge';
import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from './LanguageSwitcher';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/', permission: 'dashboard.view' },
  { icon: HardDrive, label: 'Assets', path: '/assets', permission: 'asset.view' },
  { icon: User, label: 'Users', path: '/users', permission: 'user.view' },
  { icon: Ticket, label: 'Tickets', path: '/tickets', permission: 'ticket.view' },
  { icon: ShoppingCart, label: 'Procurement', path: '/procurement', permission: 'procurement.view' },
  { icon: Package, label: 'Spare Parts', path: '/inventory/spare-parts', permission: 'inventory.view' },
  { icon: GitBranch, label: 'Workflow', path: '/workflow', permission: 'workflow.view' },
  { icon: Scale, label: 'Reconciliation', path: '/reconciliation', permission: 'reconciliation.view' },
  { icon: BarChart3, label: 'Reports', path: '/reports', permission: 'report.view' },
  { icon: ShieldX, label: 'Blacklist', path: '/blacklist', permission: 'blacklist.view' },
  { icon: History, label: 'Audit Log', path: '/audit-log', permission: 'audit.view' },
  { icon: ShieldCheck, label: 'RBAC', path: '/rbac', permission: 'rbac.view' },
  { icon: Settings, label: 'Settings', path: '/settings', permission: 'settings.view' },
];

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, hasPermission } = useAuthStore();
  const { notifications } = useNotifications();
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(true);

  const localizedNavItems = navItems.map(item => ({
    ...item,
    label: t(`menu.${item.label.toLowerCase().replace(' ', '_')}`)
  }));

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className={`${isSidebarOpen ? 'w-64' : 'w-20'} bg-card border-r transition-all duration-300 flex flex-col z-50`}>
        <div className="p-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-black text-xl tracking-tighter">
            <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground">C</div>
            {isSidebarOpen && <span>CITMS <span className="text-primary">3.6</span></span>}
          </Link>
          <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="lg:hidden">
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          {localizedNavItems.map((item) => {
            if (item.permission && !hasPermission(item.permission)) return null;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-all group ${
                  isActive 
                    ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/20' 
                    : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <item.icon className={`h-5 w-5 shrink-0 ${isActive ? '' : 'group-hover:scale-110 transition-transform'}`} />
                {isSidebarOpen && <span className="text-sm font-medium">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t">
          <Button variant="ghost" className="w-full justify-start gap-3 text-red-500 hover:text-red-600 hover:bg-red-500/10 rounded-xl" onClick={logout}>
            <LogOut className="h-5 w-5" />
            {isSidebarOpen && <span className="text-sm font-medium">{t('common.logout')}</span>}
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b bg-card/50 backdrop-blur-xl flex items-center justify-between px-8 z-40">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="hidden lg:flex">
              <Menu className="h-5 w-5" />
            </Button>
            <div className="h-4 w-[1px] bg-border hidden lg:block" />
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest hidden sm:block">
              {navItems.find(i => i.path === location.pathname)?.label || 'System'}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <div className="h-4 w-[1px] bg-border" />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative">
                  <Bell className="h-5 w-5" />
                  {unreadCount > 0 && (
                    <Badge className="absolute -top-1 -right-1 h-4 w-4 p-0 flex items-center justify-center bg-red-500 text-[10px]">
                      {unreadCount}
                    </Badge>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel>Notifications</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-xs text-muted-foreground italic">No notifications</div>
                  ) : (
                    notifications.map((n, i) => (
                      <DropdownMenuItem key={i} className="p-4 flex flex-col items-start gap-1 cursor-pointer">
                        <div className="flex items-center justify-between w-full">
                          <span className="font-bold text-xs">{n.title}</span>
                          <span className="text-[10px] text-muted-foreground">{new Date(n.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground line-clamp-2">{n.message}</p>
                      </DropdownMenuItem>
                    ))
                  )}
                </div>
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2 rounded-full pl-1 pr-3">
                  <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                    {user?.full_name?.[0] || 'U'}
                  </div>
                  <span className="text-xs font-bold hidden sm:block">{user?.full_name || 'User'}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate('/settings')}>Profile Settings</DropdownMenuItem>
                <DropdownMenuItem onClick={logout}>Logout</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto bg-muted/20">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
