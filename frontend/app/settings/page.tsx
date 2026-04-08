"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Settings, Shield, Bell, Key, Zap } from "lucide-react";
import type { AutoTradeSettings } from "@/lib/types";
import { getAutoTradeSettings, updateAutoTradeSettings } from "@/lib/api";

function SettingRow({ label, description, defaultValue, unit }: {
  label: string;
  description: string;
  defaultValue: string;
  unit?: string;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        <Input defaultValue={defaultValue} className="w-20 text-right" />
        {unit && <span className="text-sm text-muted-foreground w-8">{unit}</span>}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [autoTrade, setAutoTrade] = useState<AutoTradeSettings>({
    enabled: false, min_confidence: 70, min_edge_pct: 5.0, size_usd: 5.0,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getAutoTradeSettings().then(setAutoTrade).catch(() => {});
  }, []);

  const handleToggle = async () => {
    const updated = { ...autoTrade, enabled: !autoTrade.enabled };
    setSaving(true);
    try {
      const result = await updateAutoTradeSettings(updated);
      setAutoTrade(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  };

  const handleSaveAutoTrade = async () => {
    setSaving(true);
    try {
      const result = await updateAutoTradeSettings(autoTrade);
      setAutoTrade(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {}
    setSaving(false);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Settings className="h-6 w-6" /> 设置
      </h2>

      {/* Auto Trade */}
      <Card className={autoTrade.enabled ? "border-green-500 border-2" : ""}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <Zap className="h-5 w-5" /> 自动下单
                {autoTrade.enabled && <Badge className="bg-green-600">已开启</Badge>}
                {!autoTrade.enabled && <Badge variant="secondary">已关闭</Badge>}
              </CardTitle>
              <CardDescription className="mt-1">
                开启后，扫描器发现满足条件的信号会自动创建订单
              </CardDescription>
            </div>
            <Button
              onClick={handleToggle}
              variant={autoTrade.enabled ? "destructive" : "default"}
              disabled={saving}
            >
              {autoTrade.enabled ? "关闭自动下单" : "开启自动下单"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium">最低置信度</p>
              <p className="text-xs text-muted-foreground">信号置信度达到此值才自动下单</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={autoTrade.min_confidence}
                onChange={(e) => setAutoTrade({ ...autoTrade, min_confidence: Number(e.target.value) || 0 })}
                className="w-20 text-right"
              />
              <span className="text-sm text-muted-foreground w-8">%</span>
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium">最低边际</p>
              <p className="text-xs text-muted-foreground">信号边际利润达到此值才自动下单</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={autoTrade.min_edge_pct}
                onChange={(e) => setAutoTrade({ ...autoTrade, min_edge_pct: Number(e.target.value) || 0 })}
                className="w-20 text-right"
              />
              <span className="text-sm text-muted-foreground w-8">%</span>
            </div>
          </div>
          <Separator />
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium">单笔金额</p>
              <p className="text-xs text-muted-foreground">每笔自动下单的投入金额</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={autoTrade.size_usd}
                onChange={(e) => setAutoTrade({ ...autoTrade, size_usd: Number(e.target.value) || 0 })}
                className="w-20 text-right"
              />
              <span className="text-sm text-muted-foreground w-8">$</span>
            </div>
          </div>
          <div className="pt-4 flex items-center justify-between">
            {saved && <span className="text-sm text-green-600">已保存</span>}
            {!saved && <span />}
            <Button onClick={handleSaveAutoTrade} disabled={saving}>
              {saving ? "保存中..." : "保存自动下单设置"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Risk Management */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5" /> 风控管理
          </CardTitle>
          <CardDescription>配置交易风控参数</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          <SettingRow label="单笔限额" description="单笔交易不超过总资金的百分比" defaultValue="10" unit="%" />
          <Separator />
          <SettingRow label="日亏损上限" description="当日亏损超过此比例时暂停交易" defaultValue="5" unit="%" />
          <Separator />
          <SettingRow label="持仓集中度" description="单个市场的最大持仓占比" defaultValue="20" unit="%" />
          <Separator />
          <SettingRow label="最小边际" description="套利信号的最小利润边际" defaultValue="1.0" unit="%" />
          <Separator />
          <SettingRow label="最大持仓数" description="同时持有的最大市场数量" defaultValue="10" />
          <Separator />
          <SettingRow label="到期缓冲" description="市场到期前多少小时内不开新仓" defaultValue="24" unit="时" />
          <div className="pt-4 flex justify-end">
            <Button>保存风控设置</Button>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Key className="h-5 w-5" /> API 配置
          </CardTitle>
          <CardDescription>Polymarket API 凭证（存储在本地 .env 文件）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">API 密钥</label>
            <Input type="password" placeholder="输入 Polymarket API 密钥" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">API 秘钥</label>
            <Input type="password" placeholder="输入 Polymarket API 秘钥" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">钱包私钥</label>
            <Input type="password" placeholder="输入钱包私钥" className="mt-1" />
          </div>
          <p className="text-xs text-muted-foreground">
            凭证仅存储在本地 .env 文件中，不会传输到任何外部服务器。
          </p>
          <div className="flex justify-end">
            <Button>保存 API 设置</Button>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Bell className="h-5 w-5" /> 通知
          </CardTitle>
          <CardDescription>配置 Telegram 推送通知（可选）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium">Telegram Bot Token</label>
            <Input placeholder="输入 Telegram 机器人令牌" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">Telegram Chat ID</label>
            <Input placeholder="输入 Telegram 聊天 ID" className="mt-1" />
          </div>
          <div className="flex justify-end">
            <Button variant="outline">测试通知</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
