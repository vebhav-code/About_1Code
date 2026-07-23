-- Update rules for existing seeded authentication-debug challenge
UPDATE challenges
SET rules = 'AI tools are allowed. Debug directly in the in-browser editor and chat with the AI assistant for help. Your code and conversation are saved automatically. You get one submission.'
WHERE slug = 'authentication-debug';
