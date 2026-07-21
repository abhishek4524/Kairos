import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Users, MessageSquare, Bot, Activity, X, Lock, KeyRound, ListTree } from 'lucide-react';

const COLORS = ['#8b5cf6', '#ec4899', '#10b981', '#f43f5e', '#3b82f6', '#eab308', '#14b8a6'];

const AVATAR_NAMES = {
  'avatar.vrm': 'Kavya',
  'avatar1.vrm': 'Shriya',
  'avatar2.vrm': 'Kumar',
  'avatar3.vrm': 'Lucy',
  'avatar4.vrm': 'Sara',
  'avatar5.vrm': 'Aanya',
  'avatar6.vrm': 'Ankur'
};

export default function AdminDashboard({ onClose, theme = 'dark' }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [stats, setStats] = useState({ total_users: 0, total_messages: 0, total_assistant_messages: 0 });
  const [activity, setActivity] = useState([]);
  const [avatars, setAvatars] = useState([]);
  const [logs, setLogs] = useState([]);

  const fetchDashboardData = async (adminPassword) => {
    setLoading(true);
    setError('');
    
    const headers = {
      'x-admin-password': adminPassword
    };

    try {
      // Test auth with stats
      const statsRes = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/stats`, { headers });
      if (statsRes.status === 401) {
        throw new Error('Incorrect password');
      }
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch others
      const [activityRes, avatarsRes, logsRes] = await Promise.all([
        fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/activity`, { headers }),
        fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/avatars`, { headers }),
        fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/admin/logs`, { headers })
      ]);
      
      const activityData = await activityRes.json();
      const avatarsData = await avatarsRes.json();
      const logsData = await logsRes.json();

      setActivity(activityData);
      setLogs(logsData);
      
      const mappedAvatars = avatarsData.map(item => ({
        name: AVATAR_NAMES[item.avatar_id] || item.avatar_id,
        value: item.count
      }));
      setAvatars(mappedAvatars);

      setIsAuthenticated(true);
    } catch (err) {
      setError(err.message || 'Failed to authenticate');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    if (password.trim()) {
      fetchDashboardData(password);
    }
  };

  const cardClass = "bg-[var(--surface)] backdrop-blur-xl border border-[var(--border-glass)] rounded-2xl p-6 shadow-lg";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      className={`fixed inset-0 z-50 overflow-y-auto bg-[var(--background)]/90 backdrop-blur-md p-4 md:p-8 ${theme}`}
    >
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-[var(--text-main)] brand-font tracking-wide">Platform Analytics</h1>
            <p className="text-[var(--text-muted)] mt-2">Overview of user engagement and system usage</p>
          </div>
          <button 
            onClick={onClose}
            className="w-12 h-12 rounded-full bg-[var(--surface)] hover:bg-[var(--surface-hover)] flex items-center justify-center text-[var(--text-main)] transition-colors shadow-lg border border-[var(--border-glass)]"
          >
            <X size={24} />
          </button>
        </div>

        {!isAuthenticated ? (
          <div className="flex items-center justify-center min-h-[50vh]">
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="bg-[var(--surface)] backdrop-blur-xl border border-[var(--border-glass)] rounded-2xl p-8 shadow-2xl max-w-md w-full"
            >
              <div className="flex justify-center mb-6">
                <div className="w-16 h-16 rounded-full bg-primary/20 text-primary flex items-center justify-center">
                  <Lock size={32} />
                </div>
              </div>
              <h2 className="text-2xl font-bold text-center text-[var(--text-main)] mb-2">Admin Access Required</h2>
              <p className="text-center text-[var(--text-muted)] mb-8">Please enter the master password to view platform analytics.</p>
              
              <form onSubmit={handleLogin}>
                <div className="relative mb-6">
                  <KeyRound size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password..."
                    className="w-full bg-[var(--background)] border border-[var(--border-glass)] rounded-xl py-3 pl-12 pr-4 text-[var(--text-main)] focus:outline-none focus:border-primary transition-colors"
                    autoFocus
                  />
                </div>
                {error && <div className="text-red-400 text-sm mb-4 text-center">{error}</div>}
                <button 
                  type="submit"
                  disabled={loading}
                  className="w-full bg-primary hover:bg-primary-hover text-white rounded-xl py-3 font-semibold transition-all flex items-center justify-center"
                >
                  {loading ? 'Verifying...' : 'Unlock Dashboard'}
                </button>
              </form>
            </motion.div>
          </div>
        ) : (
          <>
            {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className={`${cardClass} flex items-center gap-4`}>
            <div className="w-14 h-14 rounded-xl bg-primary/20 text-primary flex items-center justify-center">
              <Users size={28} />
            </div>
            <div>
              <div className="text-[var(--text-muted)] text-sm font-medium">Total Unique Users</div>
              <div className="text-3xl font-bold text-[var(--text-main)]">{stats.total_users}</div>
            </div>
          </div>
          <div className={`${cardClass} flex items-center gap-4`}>
            <div className="w-14 h-14 rounded-xl bg-accent/20 text-accent flex items-center justify-center">
              <MessageSquare size={28} />
            </div>
            <div>
              <div className="text-[var(--text-muted)] text-sm font-medium">Total Messages</div>
              <div className="text-3xl font-bold text-[var(--text-main)]">{stats.total_messages}</div>
            </div>
          </div>
          <div className={`${cardClass} flex items-center gap-4`}>
            <div className="w-14 h-14 rounded-xl bg-secondary/20 text-secondary flex items-center justify-center">
              <Bot size={28} />
            </div>
            <div>
              <div className="text-[var(--text-muted)] text-sm font-medium">Assistant Responses</div>
              <div className="text-3xl font-bold text-[var(--text-main)]">{stats.total_assistant_messages}</div>
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Line Chart */}
          <div className={`${cardClass} lg:col-span-2 flex flex-col`}>
            <div className="flex items-center gap-2 mb-6 text-[var(--text-main)]">
              <Activity size={20} className="text-primary" />
              <h2 className="text-xl font-bold">Activity (Last 30 Days)</h2>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activity}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-glass)" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="var(--text-muted)" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val) => {
                      const d = new Date(val);
                      return `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                  />
                  <YAxis 
                    stroke="var(--text-muted)" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--surface)', 
                      borderColor: 'var(--border-glass)',
                      borderRadius: '8px',
                      color: 'var(--text-main)'
                    }} 
                    itemStyle={{ color: 'var(--primary)' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="messages" 
                    stroke="var(--primary)" 
                    strokeWidth={3}
                    dot={{ fill: 'var(--primary)', strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Pie Chart */}
          <div className={`${cardClass} flex flex-col`}>
            <div className="flex items-center gap-2 mb-6 text-[var(--text-main)]">
              <Users size={20} className="text-accent" />
              <h2 className="text-xl font-bold">Character Popularity</h2>
            </div>
            <div className="h-[300px] w-full flex items-center justify-center">
              {avatars.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={avatars}
                      cx="50%"
                      cy="45%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                    >
                      {avatars.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip 
                      contentStyle={{ 
                        backgroundColor: 'var(--surface)', 
                        borderColor: 'var(--border-glass)',
                        borderRadius: '8px',
                        color: 'var(--text-main)'
                      }} 
                    />
                    <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-[var(--text-muted)] text-sm">No data available</div>
              )}
            </div>
          </div>
        </div>

        {/* Detailed Logs Table */}
        <div className={`${cardClass} mt-6 mb-8`}>
          <div className="flex items-center gap-2 mb-6 text-[var(--text-main)]">
            <ListTree size={20} className="text-secondary" />
            <h2 className="text-xl font-bold">Recent Detailed Activity</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--text-muted)]">
              <thead className="text-xs uppercase bg-[var(--background)] text-[var(--text-main)]">
                <tr>
                  <th scope="col" className="px-6 py-3 rounded-tl-lg">Time</th>
                  <th scope="col" className="px-6 py-3">User ID</th>
                  <th scope="col" className="px-6 py-3">Character</th>
                  <th scope="col" className="px-6 py-3">Role</th>
                  <th scope="col" className="px-6 py-3 rounded-tr-lg">Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-[var(--border-glass)] hover:bg-[var(--surface-hover)] transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      {new Date(log.timestamp * 1000).toLocaleString(undefined, {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">
                      {log.user_id.substring(0, 15)}...
                    </td>
                    <td className="px-6 py-4">
                      {AVATAR_NAMES[log.avatar_id] || log.avatar_id}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        log.role === 'assistant' 
                          ? 'bg-secondary/20 text-secondary' 
                          : 'bg-primary/20 text-primary'
                      }`}>
                        {log.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-xs md:max-w-md truncate" title={log.content}>
                      {log.content}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center">No activity found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        </>
        )}
      </div>
    </motion.div>
  );
}
