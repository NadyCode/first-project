// ============================================================
// Horizontal Scrolling Shooter Game
// ============================================================

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const overlay = document.getElementById('overlay');
const scoreDisplay = document.getElementById('scoreDisplay');
const lifeDisplay = document.getElementById('lifeDisplay');

// --- Constants ---
const WIDTH = 800;
const HEIGHT = 500;
canvas.width = WIDTH;
canvas.height = HEIGHT;

const PLAYER_SPEED = 5;
const BULLET_SPEED = 10;
const ENEMY_BULLET_SPEED = 5;
const MAX_LIVES = 3;
const INVINCIBLE_DURATION = 90; // frames
const SHOOT_COOLDOWN = 8; // frames

// --- Game State ---
let state = 'title'; // title | playing | gameover
let score = 0;
let lives = MAX_LIVES;
let frameCount = 0;
let difficulty = 1;
let screenShake = 0;

// --- Input ---
const keys = {};
window.addEventListener('keydown', e => {
    keys[e.code] = true;
    if (e.code === 'Space') e.preventDefault();
    if (state === 'title' && e.code === 'Space') startGame();
    if (state === 'gameover' && e.code === 'Space') resetToTitle();
});
window.addEventListener('keyup', e => {
    keys[e.code] = false;
});

// --- Stars (background) ---
class Star {
    constructor() {
        this.reset(true);
    }
    reset(randomX) {
        this.x = randomX ? Math.random() * WIDTH : WIDTH + Math.random() * 50;
        this.y = Math.random() * HEIGHT;
        this.size = Math.random() * 2 + 0.5;
        this.speed = this.size * 0.8 + 0.3;
        this.brightness = Math.random() * 155 + 100;
    }
    update() {
        this.x -= this.speed;
        if (this.x < -5) this.reset(false);
    }
    draw() {
        ctx.fillStyle = `rgba(${this.brightness}, ${this.brightness}, ${this.brightness + 50}, ${this.size / 2.5})`;
        ctx.fillRect(this.x, this.y, this.size, this.size);
    }
}

// --- Player ---
const player = {
    x: 80,
    y: HEIGHT / 2,
    width: 40,
    height: 20,
    invincible: 0,
    shootCooldown: 0,
    engineFlicker: 0,

    update() {
        // Movement
        let dx = 0, dy = 0;
        if (keys['ArrowUp'] || keys['KeyW']) dy = -PLAYER_SPEED;
        if (keys['ArrowDown'] || keys['KeyS']) dy = PLAYER_SPEED;
        if (keys['ArrowLeft'] || keys['KeyA']) dx = -PLAYER_SPEED;
        if (keys['ArrowRight'] || keys['KeyD']) dx = PLAYER_SPEED;

        // Diagonal speed normalization
        if (dx !== 0 && dy !== 0) {
            dx *= 0.707;
            dy *= 0.707;
        }

        this.x = Math.max(5, Math.min(WIDTH * 0.45, this.x + dx));
        this.y = Math.max(10, Math.min(HEIGHT - 10, this.y + dy));

        // Shooting
        if (this.shootCooldown > 0) this.shootCooldown--;
        if ((keys['Space'] || keys['KeyZ']) && this.shootCooldown === 0) {
            bullets.push(new Bullet(this.x + this.width / 2 + 5, this.y));
            this.shootCooldown = SHOOT_COOLDOWN;
        }

        if (this.invincible > 0) this.invincible--;
        this.engineFlicker++;
    },

    draw() {
        if (this.invincible > 0 && Math.floor(this.invincible / 3) % 2 === 0) return;

        const x = this.x;
        const y = this.y;

        // Engine flame
        const flameLen = 8 + Math.sin(this.engineFlicker * 0.5) * 5;
        ctx.beginPath();
        ctx.moveTo(x - 5, y - 4);
        ctx.lineTo(x - 5 - flameLen, y);
        ctx.lineTo(x - 5, y + 4);
        ctx.closePath();
        ctx.fillStyle = '#f80';
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(x - 5, y - 2);
        ctx.lineTo(x - 5 - flameLen * 0.6, y);
        ctx.lineTo(x - 5, y + 2);
        ctx.closePath();
        ctx.fillStyle = '#ff0';
        ctx.fill();

        // Ship body
        ctx.beginPath();
        ctx.moveTo(x + this.width / 2 + 8, y);           // nose
        ctx.lineTo(x + this.width / 2 - 5, y - 6);
        ctx.lineTo(x - this.width / 2, y - 8);            // top-left wing
        ctx.lineTo(x - this.width / 2 + 5, y - 3);
        ctx.lineTo(x - this.width / 2 + 5, y + 3);
        ctx.lineTo(x - this.width / 2, y + 8);            // bottom-left wing
        ctx.lineTo(x + this.width / 2 - 5, y + 6);
        ctx.closePath();
        ctx.fillStyle = '#0cf';
        ctx.fill();
        ctx.strokeStyle = '#0ff';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Cockpit
        ctx.beginPath();
        ctx.arc(x + 5, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#aef';
        ctx.fill();
    },

    hitbox() {
        return { x: this.x - 12, y: this.y - 7, w: 30, h: 14 };
    }
};

// --- Bullet (player) ---
class Bullet {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.width = 14;
        this.height = 3;
        this.alive = true;
    }
    update() {
        this.x += BULLET_SPEED;
        if (this.x > WIDTH + 20) this.alive = false;
    }
    draw() {
        ctx.fillStyle = '#0ff';
        ctx.shadowColor = '#0ff';
        ctx.shadowBlur = 8;
        ctx.fillRect(this.x - this.width / 2, this.y - this.height / 2, this.width, this.height);
        ctx.shadowBlur = 0;
    }
    hitbox() {
        return { x: this.x - this.width / 2, y: this.y - this.height / 2, w: this.width, h: this.height };
    }
}

// --- Enemy bullet ---
class EnemyBullet {
    constructor(x, y, vx, vy) {
        this.x = x;
        this.y = y;
        this.vx = vx;
        this.vy = vy;
        this.radius = 4;
        this.alive = true;
    }
    update() {
        this.x += this.vx;
        this.y += this.vy;
        if (this.x < -20 || this.x > WIDTH + 20 || this.y < -20 || this.y > HEIGHT + 20) {
            this.alive = false;
        }
    }
    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#f44';
        ctx.shadowColor = '#f44';
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
    }
    hitbox() {
        return { x: this.x - this.radius, y: this.y - this.radius, w: this.radius * 2, h: this.radius * 2 };
    }
}

// --- Enemies ---
class Enemy {
    constructor(type) {
        this.type = type;
        this.alive = true;
        this.flashTimer = 0;
        this.shootTimer = 0;

        if (type === 'small') {
            this.x = WIDTH + 30;
            this.y = Math.random() * (HEIGHT - 60) + 30;
            this.width = 24;
            this.height = 16;
            this.hp = 1;
            this.speed = 2 + Math.random() * 1.5 + difficulty * 0.2;
            this.score = 100;
            this.waveAmp = Math.random() * 30 + 10;
            this.waveFreq = Math.random() * 0.04 + 0.02;
            this.baseY = this.y;
            this.phase = Math.random() * Math.PI * 2;
        } else if (type === 'medium') {
            this.x = WIDTH + 40;
            this.y = Math.random() * (HEIGHT - 80) + 40;
            this.width = 36;
            this.height = 24;
            this.hp = 3;
            this.speed = 1.2 + difficulty * 0.15;
            this.score = 300;
            this.shootInterval = Math.max(60, 120 - difficulty * 5);
            this.shootTimer = Math.floor(Math.random() * this.shootInterval);
        } else if (type === 'boss') {
            this.x = WIDTH + 60;
            this.y = HEIGHT / 2;
            this.width = 60;
            this.height = 50;
            this.hp = 20 + difficulty * 5;
            this.maxHp = this.hp;
            this.speed = 0.8;
            this.score = 2000;
            this.shootInterval = Math.max(20, 50 - difficulty * 3);
            this.shootTimer = 0;
            this.movePhase = 0;
            this.entered = false;
        }
    }

    update() {
        if (this.flashTimer > 0) this.flashTimer--;

        if (this.type === 'small') {
            this.x -= this.speed;
            this.phase += this.waveFreq;
            this.y = this.baseY + Math.sin(this.phase) * this.waveAmp;
            if (this.x < -40) this.alive = false;

        } else if (this.type === 'medium') {
            this.x -= this.speed;
            if (this.x < -50) this.alive = false;

            this.shootTimer++;
            if (this.shootTimer >= this.shootInterval && this.x < WIDTH - 50) {
                this.shootTimer = 0;
                const angle = Math.atan2(player.y - this.y, player.x - this.x);
                enemyBullets.push(new EnemyBullet(
                    this.x - this.width / 2,
                    this.y,
                    Math.cos(angle) * ENEMY_BULLET_SPEED,
                    Math.sin(angle) * ENEMY_BULLET_SPEED
                ));
            }

        } else if (this.type === 'boss') {
            if (!this.entered) {
                this.x -= this.speed;
                if (this.x <= WIDTH - 100) {
                    this.x = WIDTH - 100;
                    this.entered = true;
                }
            } else {
                this.movePhase += 0.02;
                this.y = HEIGHT / 2 + Math.sin(this.movePhase) * (HEIGHT / 3);
                this.y = Math.max(this.height / 2 + 10, Math.min(HEIGHT - this.height / 2 - 10, this.y));
            }

            this.shootTimer++;
            if (this.entered && this.shootTimer >= this.shootInterval) {
                this.shootTimer = 0;
                // Spread shot
                for (let i = -2; i <= 2; i++) {
                    const angle = Math.PI + i * 0.2;
                    enemyBullets.push(new EnemyBullet(
                        this.x - this.width / 2,
                        this.y,
                        Math.cos(angle) * ENEMY_BULLET_SPEED,
                        Math.sin(angle) * ENEMY_BULLET_SPEED
                    ));
                }
            }
        }
    }

    draw() {
        const x = this.x;
        const y = this.y;
        const flash = this.flashTimer > 0;

        if (this.type === 'small') {
            ctx.beginPath();
            ctx.moveTo(x - this.width / 2 - 5, y);
            ctx.lineTo(x, y - this.height / 2 - 3);
            ctx.lineTo(x + this.width / 2, y);
            ctx.lineTo(x, y + this.height / 2 + 3);
            ctx.closePath();
            ctx.fillStyle = flash ? '#fff' : '#f80';
            ctx.fill();
            ctx.strokeStyle = '#fa0';
            ctx.lineWidth = 1;
            ctx.stroke();

        } else if (this.type === 'medium') {
            // Hexagonal shape
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
                const angle = (Math.PI / 3) * i - Math.PI / 6;
                const px = x + Math.cos(angle) * this.width / 2;
                const py = y + Math.sin(angle) * this.height / 2;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            }
            ctx.closePath();
            ctx.fillStyle = flash ? '#fff' : '#c44';
            ctx.fill();
            ctx.strokeStyle = '#f66';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            // Eye
            ctx.beginPath();
            ctx.arc(x - 4, y, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#ff0';
            ctx.fill();

        } else if (this.type === 'boss') {
            // Body
            ctx.beginPath();
            ctx.moveTo(x - this.width / 2 - 10, y);
            ctx.lineTo(x - this.width / 2 + 10, y - this.height / 2 - 5);
            ctx.lineTo(x + this.width / 2, y - this.height / 3);
            ctx.lineTo(x + this.width / 2 + 5, y);
            ctx.lineTo(x + this.width / 2, y + this.height / 3);
            ctx.lineTo(x - this.width / 2 + 10, y + this.height / 2 + 5);
            ctx.closePath();
            ctx.fillStyle = flash ? '#fff' : '#808';
            ctx.fill();
            ctx.strokeStyle = '#f0f';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Core
            ctx.beginPath();
            ctx.arc(x, y, 10, 0, Math.PI * 2);
            ctx.fillStyle = flash ? '#fff' : '#f0f';
            ctx.shadowColor = '#f0f';
            ctx.shadowBlur = 10;
            ctx.fill();
            ctx.shadowBlur = 0;

            // HP bar
            const barW = 80;
            const barH = 6;
            const barX = x - barW / 2;
            const barY = y - this.height / 2 - 18;
            ctx.fillStyle = '#333';
            ctx.fillRect(barX, barY, barW, barH);
            ctx.fillStyle = '#f0f';
            ctx.fillRect(barX, barY, barW * (this.hp / this.maxHp), barH);
            ctx.strokeStyle = '#f0f';
            ctx.lineWidth = 1;
            ctx.strokeRect(barX, barY, barW, barH);
        }
    }

    hitbox() {
        const hw = this.width / 2;
        const hh = this.height / 2;
        return { x: this.x - hw, y: this.y - hh, w: this.width, h: this.height };
    }
}

// --- Explosion particles ---
class Particle {
    constructor(x, y, color) {
        this.x = x;
        this.y = y;
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 4 + 1;
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed;
        this.life = Math.floor(Math.random() * 20 + 15);
        this.maxLife = this.life;
        this.size = Math.random() * 3 + 1;
        this.color = color;
    }
    update() {
        this.x += this.vx;
        this.y += this.vy;
        this.vx *= 0.97;
        this.vy *= 0.97;
        this.life--;
    }
    draw() {
        const alpha = this.life / this.maxLife;
        ctx.globalAlpha = alpha;
        ctx.fillStyle = this.color;
        ctx.fillRect(this.x - this.size / 2, this.y - this.size / 2, this.size, this.size);
        ctx.globalAlpha = 1;
    }
}

// --- Collections ---
let stars = [];
let bullets = [];
let enemies = [];
let enemyBullets = [];
let particles = [];
let spawnTimer = 0;
let bossSpawned = false;
let bossDefeated = false;
let waveEnemiesKilled = 0;
let waveThreshold = 15;

// --- Collision ---
function aabb(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function spawnExplosion(x, y, color, count) {
    for (let i = 0; i < count; i++) {
        particles.push(new Particle(x, y, color));
    }
    screenShake = 6;
}

// --- Init ---
function initStars() {
    stars = [];
    for (let i = 0; i < 120; i++) {
        stars.push(new Star());
    }
}

function startGame() {
    state = 'playing';
    score = 0;
    lives = MAX_LIVES;
    frameCount = 0;
    difficulty = 1;
    player.x = 80;
    player.y = HEIGHT / 2;
    player.invincible = INVINCIBLE_DURATION;
    player.shootCooldown = 0;
    bullets = [];
    enemies = [];
    enemyBullets = [];
    particles = [];
    spawnTimer = 0;
    bossSpawned = false;
    bossDefeated = false;
    waveEnemiesKilled = 0;
    waveThreshold = 15;
    overlay.classList.add('hidden');
    updateUI();
}

function resetToTitle() {
    state = 'title';
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
        <h1>HORIZONTAL SHOOTER</h1>
        <p>Arrow Keys / WASD : Move</p>
        <p>Space / Z : Shoot</p>
        <p class="start-msg">Press SPACE to Start</p>
    `;
}

function gameOver() {
    state = 'gameover';
    overlay.classList.remove('hidden');
    overlay.innerHTML = `
        <h2>GAME OVER</h2>
        <p>SCORE: ${score}</p>
        <p class="start-msg">Press SPACE to Return to Title</p>
    `;
}

function updateUI() {
    scoreDisplay.textContent = `SCORE: ${score}`;
    let lifeStr = 'LIFE: ';
    for (let i = 0; i < MAX_LIVES; i++) {
        lifeStr += i < lives ? '\u2665 ' : '\u2661 ';
    }
    lifeDisplay.textContent = lifeStr;
}

// --- Spawn logic ---
function spawnEnemies() {
    spawnTimer++;

    // Check boss spawn
    if (waveEnemiesKilled >= waveThreshold && !bossSpawned) {
        bossSpawned = true;
        enemies.push(new Enemy('boss'));
        return;
    }

    if (bossSpawned) return; // no more spawning during boss

    const spawnRate = Math.max(20, 60 - difficulty * 3);
    if (spawnTimer >= spawnRate) {
        spawnTimer = 0;
        const rand = Math.random();
        if (rand < 0.65) {
            enemies.push(new Enemy('small'));
        } else {
            enemies.push(new Enemy('medium'));
        }
    }
}

// --- Main update ---
function update() {
    frameCount++;

    // Increase difficulty over time
    difficulty = 1 + Math.floor(frameCount / 600);

    stars.forEach(s => s.update());

    if (state !== 'playing') return;

    player.update();
    spawnEnemies();

    bullets.forEach(b => b.update());
    enemies.forEach(e => e.update());
    enemyBullets.forEach(b => b.update());
    particles.forEach(p => p.update());

    // Remove dead
    bullets = bullets.filter(b => b.alive);
    enemies = enemies.filter(e => e.alive);
    enemyBullets = enemyBullets.filter(b => b.alive);
    particles = particles.filter(p => p.life > 0);

    // Bullet -> Enemy collision
    for (const b of bullets) {
        for (const e of enemies) {
            if (b.alive && e.alive && aabb(b.hitbox(), e.hitbox())) {
                b.alive = false;
                e.hp--;
                e.flashTimer = 4;
                if (e.hp <= 0) {
                    e.alive = false;
                    score += e.score;
                    const color = e.type === 'boss' ? '#f0f' : (e.type === 'medium' ? '#f66' : '#fa0');
                    const count = e.type === 'boss' ? 60 : (e.type === 'medium' ? 25 : 12);
                    spawnExplosion(e.x, e.y, color, count);

                    if (e.type !== 'boss') {
                        waveEnemiesKilled++;
                    } else {
                        // Boss defeated - new wave
                        bossSpawned = false;
                        bossDefeated = true;
                        waveEnemiesKilled = 0;
                        waveThreshold += 5;
                        score += 3000; // wave clear bonus
                        // Clear enemy bullets on boss defeat
                        enemyBullets = [];
                    }
                    updateUI();
                }
            }
        }
    }

    // Enemy / EnemyBullet -> Player collision
    if (player.invincible === 0) {
        const ph = player.hitbox();

        for (const e of enemies) {
            if (e.alive && aabb(ph, e.hitbox())) {
                playerHit();
                break;
            }
        }

        if (player.invincible === 0) {
            for (const b of enemyBullets) {
                if (b.alive && aabb(ph, b.hitbox())) {
                    b.alive = false;
                    playerHit();
                    break;
                }
            }
        }
    }

    if (screenShake > 0) screenShake--;
}

function playerHit() {
    lives--;
    updateUI();
    spawnExplosion(player.x, player.y, '#0ff', 20);
    if (lives <= 0) {
        gameOver();
    } else {
        player.invincible = INVINCIBLE_DURATION;
    }
}

// --- Render ---
function draw() {
    ctx.save();
    if (screenShake > 0) {
        ctx.translate(
            (Math.random() - 0.5) * screenShake * 2,
            (Math.random() - 0.5) * screenShake * 2
        );
    }

    // Background
    ctx.fillStyle = '#0a0a1a';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    stars.forEach(s => s.draw());

    if (state === 'playing') {
        player.draw();
        bullets.forEach(b => b.draw());
        enemies.forEach(e => e.draw());
        enemyBullets.forEach(b => b.draw());
        particles.forEach(p => p.draw());
    }

    ctx.restore();
}

// --- Game Loop ---
initStars();
updateUI();

function gameLoop() {
    update();
    draw();
    requestAnimationFrame(gameLoop);
}

gameLoop();
