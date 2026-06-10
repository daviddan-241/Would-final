import { Router } from "express";
import { db } from "@workspace/db";
import { profiles, targets, ads, accounts, discordCoins, settingsTable, analyticsTable, growthCampaigns, conversations, autoReplies } from "@workspace/db";
import { desc } from "drizzle-orm";

const router = Router();

router.get("/data", async (_req, res) => {
  try {
    const [
      allProfiles,
      allTargets,
      allAds,
      allAccounts,
      allCoins,
      settingsRows,
      analyticsRows,
      allCampaigns,
      allConvs,
      allReplies,
    ] = await Promise.all([
      db.select().from(profiles).orderBy(profiles.createdAt),
      db.select().from(targets).orderBy(targets.createdAt),
      db.select().from(ads).orderBy(ads.createdAt),
      db.select().from(accounts).orderBy(accounts.createdAt),
      db.select().from(discordCoins).orderBy(desc(discordCoins.foundAt)).limit(100),
      db.select().from(settingsTable).limit(1),
      db.select().from(analyticsTable).limit(1),
      db.select().from(growthCampaigns).orderBy(growthCampaigns.createdAt),
      db.select().from(conversations).orderBy(desc(conversations.lastMessageTime)),
      db.select().from(autoReplies).orderBy(autoReplies.createdAt),
    ]);

    // Ensure analytics row exists with default values
    let analytics = analyticsRows[0];
    if (!analytics) {
      const [row] = await db.insert(analyticsTable).values({ impressions: 24500, clicks: 1820, leads: 412, conversionRate: 22.6 }).returning();
      analytics = row;
    }

    // Ensure settings row exists
    let settings = settingsRows[0];
    if (!settings) {
      const [row] = await db.insert(settingsTable).values({}).returning();
      settings = row;
    }

    const unreadCount = allConvs.reduce((sum, c) => sum + (c.unread ?? 0), 0);

    res.json({
      profiles: allProfiles.map(p => ({
        id: p.id, name: p.name, niche: p.niche, bio: p.bio,
        cta_link: p.ctaLink, ai_tone: p.aiTone, avatar: p.avatar,
        active: p.active, tg_bot_token: p.tgBotToken, tg_chat_id: p.tgChatId,
      })),
      targets: allTargets.map(t => ({ id: t.id, platform: t.platform, handle: t.handle, destination: t.destination, active: t.active, last_post_id: t.lastPostId, last_checked: t.lastChecked })),
      ads: allAds.map(a => ({ id: a.id, platform: a.platform, content: a.content, interval_min: a.intervalMin, image_url: a.imageUrl, active: a.active, last_posted: a.lastPosted })),
      accounts: allAccounts.map(a => ({ id: a.id, platform: a.platform, username: a.username, status: a.status })),
      discord_coins: allCoins.map(c => ({ id: c.id, name: c.name, symbol: c.symbol, mint: c.mint, chain: c.chain, discord_link: c.discordLink, telegram_link: c.telegramLink, twitter: c.twitter, website: c.website, image_url: c.imageUrl, pair_url: c.pairUrl, source: c.source, found_at: c.foundAt })),
      growth_campaigns: allCampaigns.map(c => ({ id: c.id, niche: c.niche, keywords: c.keywords ? c.keywords.split(",").filter(Boolean) : [], cta_link: c.ctaLink, platform: c.platform, status: c.status, impressions_generated: c.impressionsGenerated, clicks_generated: c.clicksGenerated, leads_captured: c.leadsCaptured })),
      conversations: allConvs.map(c => ({ id: c.id, profile_id: c.profileId, platform: c.platform, sender_handle: c.senderHandle, avatar: c.avatar, unread: c.unread, last_message_text: c.lastMessageText, last_message_time: c.lastMessageTime })),
      auto_replies: allReplies.map(r => ({ id: r.id, keyword: r.keyword, reply_text: r.replyText, active: r.active })),
      analytics: {
        impressions: analytics.impressions,
        clicks: analytics.clicks,
        leads: analytics.leads,
        conversion_rate: analytics.conversionRate,
      },
      settings: {
        openai_key: settings.openaiKey,
        gemini_key: settings.geminiKey,
        global_cta_link: settings.globalCtaLink,
        auto_mirror_enabled: settings.autoMirrorEnabled,
        auto_raid_enabled: settings.autoRaidEnabled,
        auto_post_enabled: settings.autoPostEnabled,
        auto_dm_reply_enabled: settings.autoDmReplyEnabled,
        growth_hacks_enabled: settings.growthHacksEnabled,
        rewrite_style: settings.rewriteStyle,
        proxy_list: [],
      },
      unread_count: unreadCount,
    });
  } catch (err) {
    res.status(500).json({ success: false, error: String(err) });
  }
});

export default router;
