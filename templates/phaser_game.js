const config = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    physics: {
        default: 'arcade',
        arcade: {
            gravity: { y: 0 },
            debug: false
        }
    },
    scene: {
        preload: preload,
        create: create,
        update: update
    }
};

const game = new Phaser.Game(config);
let player;
let foodItems;
let score = 0;
let scoreText;
let gameOver = false;
const timeLimit = 30; // seconds
let timerEvent;

function preload() {}

function create() {
    player = this.physics.add.rectangle(400, 500, 50, 50, 0x00ff00);
    this.physics.add.existing(player);
    player.setCollideWorldBounds(true);

    foodItems = this.physics.add.group({
        key: 'food',
        repeat: 11,
        setXY: { x: 12, y: 0, stepX: 70 }
    });

    foodItems.children.iterate(function (child) {
        child.setCircle(20, 0, 0);
        child.setFillStyle(0xff0000);
    });

    scoreText = this.add.text(16, 16, 'Score: 0', { fontSize: '32px', fill: '#000' });

    this.physics.add.overlap(player, foodItems, collectFood, null, this);

    this.input.keyboard.on('keydown-A', () => { player.setVelocityX(-160); });
    this.input.keyboard.on('keydown-D', () => { player.setVelocityX(160); });
    this.input.keyboard.on('keyup-A', () => { if (player.body.velocity.x < 0) player.setVelocityX(0); });
    this.input.keyboard.on('keyup-D', () => { if (player.body.velocity.x > 0) player.setVelocityX(0); });
    this.input.keyboard.on('keydown-Space', jump);

    timerEvent = this.time.addEvent({
        delay: timeLimit * 1000,
        callback: endGame,
        callbackScope: this
    });
}

function update() {
    if (gameOver) return;
}

function collectFood(player, food) {
    food.destroy();
    score += 10;
    scoreText.setText('Score: ' + score);
    spawnFood();
}

function spawnFood() {
    const x = Phaser.Math.Between(0, 800);
    const food = this.physics.add.rectangle(x, 0, 40, 40, 0xff0000);
    food.setVelocityY(Phaser.Math.Between(100, 200));
    food.setCollideWorldBounds(true);
    food.setBounce(1);
    foodItems.add(food);
}

function jump() {
    if (player.body.touching.down) {
        player.setVelocityY(-330);
    }
}

function endGame() {
    gameOver = true;
    this.physics.pause();
    scoreText.setText('Game Over! Final Score: ' + score);
}